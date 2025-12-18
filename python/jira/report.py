"""
Generate status reports for Jira issues (optionally including subtasks and linked issues) using the Jira REST API.

Features:
  - Fetch issues by JQL query or direct issue keys.
  - Get subtasks and/or linked issues for each parent.
  - Derive status from Jira's native status field with emoji decoration.
  - Include target date (due date) and last update timestamps.
  - Filter issues by a minimum last-update date.
  - Emit a combined report for multiple issues or individual reports per issue.
  - Output to stdout or append/write to a specified markdown file.
  - Supports both Jira Cloud and Jira Server/Data Center.

Configuration:
  Environment variables (required):
    JIRA_SERVER      - Jira server URL (e.g., https://mycompany.atlassian.net or https://jira.company.com)
    JIRA_API_TOKEN   - Your API token or Personal Access Token (PAT)
  
  For Jira Cloud:
    JIRA_EMAIL       - Your Atlassian account email (required for Cloud)
    Generate API token at: https://id.atlassian.com/manage-profile/security/api-tokens
  
  For Jira Server/Data Center:
    JIRA_EMAIL       - Optional (your username, not email)
    Generate PAT in Jira: Profile -> Personal Access Tokens

Usage:
    python report.py [options] <issue_keys_or_jql>

Options:
    --jql <query>
        Use a JQL query to fetch issues instead of specifying issue keys.
    --include-parent
        When including subtasks/linked issues, add a dedicated parent column to the table.
    --include-subtasks
        Include subtasks of each supplied issue.
    --include-linked
        Include linked issues of each supplied issue.
    --since <date>
        Only include issues updated on or after this date (YYYY-MM-DD).
    --output-file <file>, -o <file>
        Write (or append) the markdown report to this file instead of standard output.
    --individual, -i
        Generate a separate report section (or file append) for each provided issue.
    --stdin, -s
        Read issue keys from standard input (one per line). Useful for piping.
    --verbose, -v
        Enable verbose / debug logging.
    --quiet, -q
        Suppress non-essential output (only errors).

Examples:
    python report.py --include-subtasks --since 2025-01-01 PROJECT-123 PROJECT-456
    python report.py --jql "project = MYPROJ AND status != Done" --output-file status.md
    cat issues.txt | python report.py --stdin --include-subtasks --include-parent -o aggregated.md

Notes:
  - You must have the 'requests' Python package installed: pip install requests
  - Set the required environment variables before running.
"""
import json
import os
import re
import sys
import datetime
import traceback
import argparse
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, quote

try:
    import requests
except ImportError:
    print("ERROR: The 'requests' package is not installed.", file=sys.stderr)
    print("Please install it: pip install requests", file=sys.stderr)
    sys.exit(1)

# Set up logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Default configuration values
DEFAULT_SHOW_PARENT = False
DEFAULT_PAGE_SIZE = 50  # Jira's default max is 100

# Status categories mapped to emojis
STATUS_CATEGORIES = {
    "done": "🟣",
    "in progress": "🟢",
    "in review": "🟡",
    "ready": "⚪",
    "to do": "⚪",
    "blocked": "🔴",
}

# Map common Jira status names to our categories
STATUS_MAPPING = {
    # Done statuses
    "done": "done",
    "closed": "done",
    "resolved": "done",
    "complete": "done",
    "completed": "done",
    # In Progress statuses
    "in progress": "in progress",
    "in development": "in progress",
    "developing": "in progress",
    "active": "in progress",
    "working": "in progress",
    # Ready statuses (sorted before general To Do)
    "ready for work": "ready",
    "ready": "ready",
    "ready for dev": "ready",
    "ready for development": "ready",
    "selected for development": "ready",
    "prioritized": "ready",
    # To Do statuses
    "to do": "to do",
    "open": "to do",
    "new": "to do",
    "backlog": "to do",
    # Blocked statuses
    "blocked": "blocked",
    "on hold": "blocked",
    "waiting": "blocked",
    "impediment": "blocked",
    # Review statuses
    "in review": "in review",
    "code review": "in review",
    "review": "in review",
    "pending review": "in review",
    "awaiting review": "in review",
}


class JiraClient:
    """Simple Jira REST API client using requests. Supports Cloud and Server/Data Center."""
    
    def __init__(self, server: str, api_token: str, email: Optional[str] = None):
        self.server = server.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        
        # Detect if this is Jira Cloud or Server/Data Center
        self.is_cloud = ".atlassian.net" in server.lower()
        
        if self.is_cloud:
            # Jira Cloud: Use Basic auth with email:token, API v3
            if not email:
                raise ValueError("JIRA_EMAIL is required for Jira Cloud authentication")
            self.session.auth = (email, api_token)
            self.api_version = "3"
            logger.debug(f"Using Jira Cloud authentication (API v{self.api_version})")
        else:
            # Jira Server/Data Center: Use Bearer token (PAT), API v2
            self.session.headers["Authorization"] = f"Bearer {api_token}"
            self.api_version = "2"
            logger.debug(f"Using Jira Server/Data Center authentication (API v{self.api_version})")
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the Jira API."""
        url = urljoin(f"{self.server}/rest/api/{self.api_version}/", endpoint.lstrip('/'))
        logger.debug(f"Request: {method} {url}")
        
        response = self.session.request(method, url, **kwargs)
        
        logger.debug(f"Response: {response.status_code}")
        if response.status_code >= 400:
            logger.error(f"API error: {response.status_code} - {response.text[:500]}")
            response.raise_for_status()
        
        return response
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request and return JSON response."""
        response = self._request("GET", endpoint, params=params)
        return response.json()
    
    def get_issue(self, issue_key: str) -> Dict:
        """Get a single issue by key."""
        # Request specific fields to reduce response size
        fields = "summary,status,assignee,priority,created,updated,duedate,resolutiondate,subtasks,issuelinks"
        return self.get(f"issue/{issue_key}", params={"fields": fields})
    
    def search_issues(self, jql: str, fields: Optional[str] = None, max_results: int = 1000) -> List[Dict]:
        """
        Search for issues using JQL with proper pagination.
        
        Args:
            jql: JQL query string
            fields: Comma-separated list of fields to return
            max_results: Maximum total results to return
        
        Returns:
            List of issue dictionaries
        """
        if fields is None:
            fields = "summary,status,assignee,priority,created,updated,duedate,resolutiondate"
        
        all_issues = []
        start_at = 0
        page_size = min(DEFAULT_PAGE_SIZE, max_results)
        
        while True:
            params = {
                "jql": jql,
                "fields": fields,
                "startAt": start_at,
                "maxResults": page_size,
            }
            
            logger.debug(f"Fetching issues: startAt={start_at}, maxResults={page_size}")
            response = self.get("search", params=params)
            
            issues = response.get("issues", [])
            total = response.get("total", 0)
            
            all_issues.extend(issues)
            logger.debug(f"Fetched {len(issues)} issues (total so far: {len(all_issues)}, server total: {total})")
            
            # Check if we've fetched all issues or hit our limit
            if len(all_issues) >= total or len(all_issues) >= max_results:
                break
            
            # Check if server returned fewer than requested (last page)
            if len(issues) < page_size:
                break
            
            start_at += page_size
            
            # Don't fetch more than max_results
            remaining = max_results - len(all_issues)
            page_size = min(DEFAULT_PAGE_SIZE, remaining)
        
        logger.info(f"Fetched {len(all_issues)} issues total")
        return all_issues[:max_results]
    
    def test_connection(self) -> bool:
        """Test the connection to Jira."""
        try:
            self.get("myself")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection test failed: {e}")
            return False


def get_jira_client() -> JiraClient:
    """Create and return a Jira client using environment variables."""
    server = os.environ.get("JIRA_SERVER")
    email = os.environ.get("JIRA_EMAIL")  # Optional for Server/Data Center
    api_token = os.environ.get("JIRA_API_TOKEN")

    if not server:
        logger.error("JIRA_SERVER environment variable is not set.")
        logger.error("Example: export JIRA_SERVER=https://mycompany.atlassian.net")
        sys.exit(1)

    if not api_token:
        logger.error("JIRA_API_TOKEN environment variable is not set.")
        is_cloud = ".atlassian.net" in server.lower()
        if is_cloud:
            logger.error("For Jira Cloud: Generate token at https://id.atlassian.com/manage-profile/security/api-tokens")
        else:
            logger.error("For Jira Server/Data Center: Generate a Personal Access Token (PAT) in your Jira profile")
        sys.exit(1)
    
    is_cloud = ".atlassian.net" in server.lower()
    if is_cloud and not email:
        logger.error("JIRA_EMAIL environment variable is required for Jira Cloud.")
        logger.error("Set it to your Atlassian account email.")
        sys.exit(1)

    try:
        client = JiraClient(server, api_token, email)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    if not client.test_connection():
        logger.error("Failed to connect to Jira. Check your credentials and server URL.")
        if not is_cloud:
            logger.error("For Jira Server/Data Center, ensure you're using a valid Personal Access Token (PAT).")
            logger.error("Generate one at: Your Profile -> Personal Access Tokens")
        sys.exit(1)
    
    logger.debug(f"Connected to Jira server: {server}")
    return client


def log_json(data, message=None):
    """Helper function to log JSON data during debugging."""
    if logger.level <= logging.DEBUG:
        if message:
            logger.debug(message)
        try:
            logger.debug(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Could not format JSON: {e}")
            logger.debug(str(data))


def normalize_status(status_name: str) -> str:
    """Normalize a Jira status name to our standard categories."""
    status_lower = status_name.lower().strip()
    return STATUS_MAPPING.get(status_lower, "to do")


def get_status_emoji(status_category: str) -> str:
    """Get the emoji for a status category."""
    return STATUS_CATEGORIES.get(status_category, "❓")


def parse_jira_date(date_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parse a Jira date string into a datetime object."""
    if not date_str:
        return None
    try:
        # Jira dates can be in various formats
        # Common: 2025-01-15T10:30:00.000+0000 or 2025-01-15
        if 'T' in date_str:
            # Handle timezone offset format (e.g., +0000 -> +00:00)
            date_str = re.sub(r'(\d{2})(\d{2})$', r'\1:\2', date_str)
            return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None


def format_date(date_str: Optional[str]) -> str:
    """Format a date string for display."""
    if not date_str:
        return "N/A"
    dt = parse_jira_date(date_str)
    if dt:
        return dt.strftime("%Y-%m-%d")
    return date_str


def extract_issue_data(issue: Dict, server_url: str, parent_key: Optional[str] = None, parent_summary: Optional[str] = None) -> Dict:
    """Extract relevant data from a Jira issue API response."""
    fields = issue.get("fields", {})
    issue_key = issue.get("key", "")
    
    # Get status
    status_obj = fields.get("status", {})
    status_name = status_obj.get("name", "Unknown") if status_obj else "Unknown"
    status_category = normalize_status(status_name)
    
    # Get assignee
    assignee_obj = fields.get("assignee")
    assignee = assignee_obj.get("displayName", "Unassigned") if assignee_obj else "Unassigned"
    
    # Get priority
    priority_obj = fields.get("priority")
    priority = priority_obj.get("name", "None") if priority_obj else "None"
    
    # Get dates
    created = fields.get("created")
    updated = fields.get("updated")
    due_date = fields.get("duedate")
    resolution_date = fields.get("resolutiondate")
    
    # Get summary
    summary = fields.get("summary", "")
    
    # Build issue URL
    issue_url = f"{server_url}/browse/{issue_key}"
    
    return {
        "key": issue_key,
        "url": issue_url,
        "summary": summary,
        "status": status_category,
        "status_name": status_name,
        "assignee": assignee,
        "priority": priority,
        "created": created,
        "updated": updated,
        "due_date": due_date,
        "resolution_date": resolution_date,
        "parent_key": parent_key or issue_key,
        "parent_summary": parent_summary or summary,
        "parent_url": f"{server_url}/browse/{parent_key}" if parent_key else issue_url,
    }


def get_issue_details(client: JiraClient, issue_key: str, parent_key: Optional[str] = None, parent_summary: Optional[str] = None) -> Optional[Dict]:
    """Get issue details from Jira."""
    try:
        logger.info(f"  - Fetching: {issue_key}")
        issue = client.get_issue(issue_key)
        log_json(issue, f"Issue data for {issue_key}:")
        return extract_issue_data(issue, client.server, parent_key, parent_summary)
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch issue {issue_key}: {e}")
        return None


def get_subtasks(client: JiraClient, parent_key: str, parent_summary: Optional[str] = None) -> List[Dict]:
    """Get subtasks for a parent issue."""
    subtasks = []
    try:
        # First get the parent issue to find subtasks
        parent_issue = client.get_issue(parent_key)
        fields = parent_issue.get("fields", {})
        summary = parent_summary or fields.get("summary", "")
        
        subtask_refs = fields.get("subtasks", [])
        
        for subtask_ref in subtask_refs:
            subtask_key = subtask_ref.get("key")
            if subtask_key:
                subtask_data = get_issue_details(client, subtask_key, parent_key, summary)
                if subtask_data:
                    subtasks.append(subtask_data)
        
        logger.info(f"  Found {len(subtasks)} subtasks for {parent_key}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get subtasks for {parent_key}: {e}")
    
    return subtasks


def get_linked_issues(client: JiraClient, parent_key: str, parent_summary: Optional[str] = None) -> List[Dict]:
    """Get linked issues for a parent issue."""
    linked = []
    try:
        parent_issue = client.get_issue(parent_key)
        fields = parent_issue.get("fields", {})
        summary = parent_summary or fields.get("summary", "")
        
        issue_links = fields.get("issuelinks", [])
        
        for link in issue_links:
            # Links can be inward or outward
            linked_issue = link.get("outwardIssue") or link.get("inwardIssue")
            if linked_issue:
                linked_key = linked_issue.get("key")
                if linked_key:
                    linked_data = get_issue_details(client, linked_key, parent_key, summary)
                    if linked_data:
                        linked.append(linked_data)
        
        logger.info(f"  Found {len(linked)} linked issues for {parent_key}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get linked issues for {parent_key}: {e}")
    
    return linked


def format_timestamp_with_link(timestamp: Optional[str], issue_url: Optional[str], include_days_ago: bool = False) -> str:
    """Format a timestamp string as a markdown link with optional relative day text."""
    if not timestamp or timestamp == "N/A" or not issue_url:
        return "N/A"
    try:
        dt = parse_jira_date(timestamp)
        if not dt:
            return timestamp
        date_str = dt.strftime("%Y-%m-%d")
        days_text = ""
        if include_days_ago:
            now = datetime.datetime.now(datetime.timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            delta = now - dt
            days_ago = delta.days
            if days_ago == 0:
                days_text = "today"
            elif days_ago == 1:
                days_text = "1 day ago"
            else:
                days_text = f"{days_ago} days ago"
            days_text = f" ({days_text})"
        display_text = f"{date_str}{days_text}"
        return f"[{display_text}]({issue_url})"
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not format timestamp '{timestamp}': {e}")
        return timestamp


def render_markdown_report(
    issues: List[Dict],
    show_parent: bool = True,
    since: Optional[datetime.datetime] = None,
    title: Optional[str] = None
) -> str:
    """Render the issues as a markdown report."""
    result = []
    title = title or "Jira Status Report"
    result.append(f"\n### {title}, {datetime.datetime.now().strftime('%Y-%m-%d')}")
    
    if show_parent:
        result.append("\n| status | parent | issue | assignee | due date | last update |")
        result.append("|---|:--|:--|:--|:--|:--|")
    else:
        result.append("\n| status | issue | assignee | due date | last update |")
        result.append("|---|:--|:--|:--|:--|")
    
    filtered_issues = []
    for issue in issues:
        if since:
            is_done = issue.get("status") == "done"
            resolution_date = issue.get("resolution_date")
            timestamp = resolution_date if (is_done and resolution_date) else issue.get("updated", "N/A")
            if timestamp == "N/A" or not timestamp:
                continue
            try:
                update_date = parse_jira_date(timestamp)
                if update_date:
                    if update_date.tzinfo is None:
                        update_date = update_date.replace(tzinfo=datetime.timezone.utc)
                    if since.tzinfo is None:
                        since = since.replace(tzinfo=datetime.timezone.utc)
                    if update_date < since:
                        continue
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date '{timestamp}': {e}")
                continue
        filtered_issues.append(issue)

    def get_sort_key(issue):
        status = issue.get("status", "to do")
        status_priority = list(STATUS_CATEGORIES.keys()).index(status) if status in STATUS_CATEGORIES else 999
        due_date = issue.get("due_date") or "9999-99-99"
        if due_date == "None":
            due_date = "9999-99-99"
        last_update = issue.get("updated") or "9999-99-99"
        summary = issue.get("summary", "")
        return (status_priority, due_date, last_update, summary)

    for issue in sorted(filtered_issues, key=get_sort_key):
        url = issue.get("url", "")
        key = issue.get("key", "")
        summary = issue.get("summary", "")
        issue_link = f"[{key}: {summary}]({url})"
        
        status_category = issue.get("status", "to do")
        status_name = issue.get("status_name", status_category)
        emoji = get_status_emoji(status_category)
        status_with_emoji = f"{emoji} {status_name}"
        
        assignee = issue.get("assignee", "Unassigned")
        due_date = format_date(issue.get("due_date"))
        
        is_done = status_category == "done"
        resolution_date = issue.get("resolution_date")
        timestamp = resolution_date if (is_done and resolution_date) else issue.get("updated", "N/A")
        formatted_timestamp_link = format_timestamp_with_link(timestamp, url, False)
        
        if show_parent:
            parent_url = issue.get("parent_url", "")
            parent_key = issue.get("parent_key", "")
            parent_link = f"[{parent_key}]({parent_url})"
            row = f"| {status_with_emoji} | {parent_link} | {issue_link} | {assignee} | {due_date} | {formatted_timestamp_link} |"
        else:
            row = f"| {status_with_emoji} | {issue_link} | {assignee} | {due_date} | {formatted_timestamp_link} |"
        result.append(row)
    
    result.append("\n")
    return "\n".join(result)


def generate_report(
    client: JiraClient,
    issue_keys: List[str],
    show_parent: bool = DEFAULT_SHOW_PARENT,
    show_subtasks: bool = False,
    show_linked: bool = False,
    since: Optional[datetime.datetime] = None,
    output_file: Optional[str] = None,
    jql_query: Optional[str] = None
) -> None:
    """Generate a report of all issues with their status and metadata."""
    root_issues: List[Dict] = []
    child_issues: List[Dict] = []
    
    # If JQL query provided, use that instead of issue keys
    if jql_query:
        logger.info(f"Executing JQL query: {jql_query}")
        try:
            issues = client.search_issues(jql_query)
            # Extract data from search results
            for issue in issues:
                issue_data = extract_issue_data(issue, client.server)
                root_issues.append(issue_data)
                
                if show_subtasks or show_linked:
                    issue_key = issue.get("key")
                    parent_summary = issue_data.get("summary")
                    
                    if show_subtasks:
                        subtasks = get_subtasks(client, issue_key, parent_summary)
                        child_issues.extend(subtasks)
                    
                    if show_linked:
                        linked = get_linked_issues(client, issue_key, parent_summary)
                        child_issues.extend(linked)
            
            issue_keys = [issue.get("key") for issue in issues]
            logger.info(f"Found {len(issue_keys)} issues from JQL query")
        except requests.exceptions.RequestException as e:
            logger.error(f"JQL query failed: {e}")
            return
    else:
        # Fetch each issue individually
        parent_summary = None
        parent_key = None
        
        for issue_key in issue_keys:
            logger.info(f"Processing {issue_key}...")
            detailed_issue = get_issue_details(client, issue_key)
            if detailed_issue:
                root_issues.append(detailed_issue)
                parent_summary = detailed_issue.get("summary", issue_key)
                parent_key = issue_key
                
                if show_subtasks:
                    subtasks = get_subtasks(client, issue_key, parent_summary)
                    child_issues.extend(subtasks)
                
                if show_linked:
                    linked = get_linked_issues(client, issue_key, parent_summary)
                    child_issues.extend(linked)

    custom_title = None
    if len(issue_keys) == 1 and root_issues:
        parent_key = issue_keys[0]
        parent_summary = root_issues[0].get("summary", parent_key)
        parent_url = f"{client.server}/browse/{parent_key}"
        custom_title = f"[{parent_key}: {parent_summary}]({parent_url})"
    
    if show_subtasks or show_linked:
        markdown_report = render_markdown_report(
            issues=child_issues,
            show_parent=show_parent,
            since=since,
            title=custom_title
        )
    else:
        markdown_report = render_markdown_report(
            issues=root_issues,
            show_parent=False,
            since=since,
            title=custom_title
        )
    
    if output_file:
        try:
            file_exists = os.path.exists(output_file)
            mode = 'a' if file_exists else 'w'
            with open(output_file, mode) as f:
                if mode == 'a':
                    f.write("\n\n\n\n")
                f.write(markdown_report)
        except IOError as e:
            logger.error(f"Error writing to file {output_file}: {e}")
            print(markdown_report)
    else:
        print(markdown_report)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Generate a status report for Jira issues (and optional subtasks/linked issues)",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Environment variables:
  JIRA_SERVER     - Jira server URL (required)
  JIRA_API_TOKEN  - API token or Personal Access Token (required)
  JIRA_EMAIL      - Your email/username (required for Cloud, optional for Server)

For Jira Cloud (*.atlassian.net):
  export JIRA_SERVER="https://mycompany.atlassian.net"
  export JIRA_EMAIL="you@company.com"
  export JIRA_API_TOKEN="<token from id.atlassian.com>"

For Jira Server/Data Center:
  export JIRA_SERVER="https://jira.company.com"
  export JIRA_API_TOKEN="<Personal Access Token from Jira profile>"

Examples:
  python report.py PROJECT-123 PROJECT-456
  python report.py --jql "project = MYPROJ AND status != Done"
  python report.py --include-subtasks --since 2025-01-01 PROJECT-123
            """
        )
        parser.add_argument("issues", nargs="*", help="Jira issue keys to include in the report")
        parser.add_argument("--jql", type=str, help="JQL query to fetch issues (alternative to specifying keys)")
        parser.add_argument("--include-parent", action="store_true", help="When showing subtasks/linked, include a parent column")
        parser.add_argument("--include-subtasks", action="store_true", help="Include subtasks in the report output")
        parser.add_argument("--include-linked", action="store_true", help="Include linked issues in the report output")
        parser.add_argument("--since", type=str, help="Only include issues updated on or after this date (YYYY-MM-DD)")
        parser.add_argument("--output-file", "-o", type=str, help="Write / append the markdown report to this file")
        parser.add_argument("--individual", "-i", action="store_true", help="Generate a separate report section for each issue")
        parser.add_argument("--stdin", "-s", action="store_true", help="Read issue keys from stdin (one per line)")
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
        parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output")
        
        args = parser.parse_args()
        
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        elif args.quiet:
            logger.setLevel(logging.ERROR)
        else:
            logger.setLevel(logging.WARNING)
        
        issue_keys = args.issues.copy() if args.issues else []
        
        if args.stdin or (not issue_keys and not args.jql and not sys.stdin.isatty()):
            logger.info("Reading issue keys from stdin...")
            for line in sys.stdin:
                key = line.strip()
                if key:
                    issue_keys.append(key)
        
        if not issue_keys and not args.jql:
            parser.print_help()
            logger.error("\nNo issue keys or JQL query provided.")
            sys.exit(1)
        
        logger.info(f"Processing {len(issue_keys)} issues...")
        
        since = None
        if args.since:
            try:
                since = datetime.datetime.fromisoformat(args.since)
                since = since.replace(tzinfo=datetime.timezone.utc)
                logger.info(f"Filtering issues updated after {since}")
            except ValueError:
                logger.error(f"Invalid date format '{args.since}'. Expected YYYY-MM-DD.")
                sys.exit(1)
        
        if args.output_file and os.path.exists(args.output_file):
            try:
                os.remove(args.output_file)
                logger.info(f"Removed existing file: {args.output_file}")
            except OSError as e:
                logger.warning(f"Could not remove existing file {args.output_file}: {e}")
        
        # Connect to Jira
        client = get_jira_client()
        
        if args.individual:
            for issue_key in issue_keys:
                generate_report(
                    client=client,
                    issue_keys=[issue_key],
                    show_parent=args.include_parent,
                    show_subtasks=args.include_subtasks,
                    show_linked=args.include_linked,
                    since=since,
                    output_file=args.output_file,
                    jql_query=None  # Don't use JQL for individual mode
                )
        else:
            generate_report(
                client=client,
                issue_keys=issue_keys,
                show_parent=args.include_parent,
                show_subtasks=args.include_subtasks,
                show_linked=args.include_linked,
                since=since,
                output_file=args.output_file,
                jql_query=args.jql
            )
            
    except KeyboardInterrupt:
        logger.warning("\nOperation canceled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)
