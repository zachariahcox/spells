# This script uses the GitHub CLI to fetch sub-issues of a given list of issues.
import json
import os
import re
import subprocess
from typing import List, Dict, Tuple, Optional
import shutil
import sys
import datetime
import traceback
import argparse

# Default configuration values
DEFAULT_SHOW_PARENT = False  # Parent column is not shown by default

# standard status labels and some emojis for display
STATUS_LABELS = {
    "done": "🟣", 
    "on track": "🟢", 
    "at risk": "🟡", 
    "high risk": "🔴", 
    "inactive": "⚪", 
}

def extract_repo_and_issue_number(issue_url: str) -> Tuple[str, str]:
    """Extract repository name and issue number from a GitHub issue URL."""
    match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', issue_url)
    if match:
        repo = match.group(1)
        issue_number = match.group(2)
        return repo, issue_number
    raise ValueError(f"Invalid GitHub issue URL: {issue_url}")

def get_target_date_from_comments(
        repo: str, 
        issue_number: str
        ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract Target Date from issue comments, searching from newest to oldest.
    
    Returns:
        A tuple (target_date, comment_created_at, comment_url) where:
        - target_date: The extracted target date or None if not found
        - comment_created_at: The timestamp of the comment containing the target date or None if not found
        - comment_url: The URL of the comment containing the target date or None if not found
    """
    try:
        # Fetch comments for the issue using GitHub API
        owner, repository = repo.split('/')
        api_endpoint = f"/repos/{owner}/{repository}/issues/{issue_number}/comments"
        cmd = [
            "gh", "api", 
            "-H", "Accept: application/vnd.github+json",
            "-H", "X-GitHub-Api-Version: 2022-11-28",
            "--paginate",
            f"{api_endpoint}?sort=created&direction=desc&per_page=100"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Paginated results might come as arrays on separate lines
        try:
            content = result.stdout
            # Handle case where output is multiple JSON arrays (one per page)
            if content.strip().startswith('[') and '\n[' in content:
                all_comments = []
                for line in content.splitlines():
                    if line.strip():
                        page_comments = json.loads(line)
                        if isinstance(page_comments, list):
                            all_comments.extend(page_comments)
                comments = all_comments
            else:
                comments = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Error parsing comments JSON: {e}")
            comments = []
        
        # Sort comments by creation date (newest first)
        comments.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Look for Target Date in the HTML comments format - search through all comments from newest to oldest
        target_date_pattern = r'<!-- data key="target_date" start -->\s*(.*?)\s*<!-- data end -->'
        
        # Check all comments starting with the most recent one
        for comment in comments:
            body = comment.get("body", "")
            match = re.search(target_date_pattern, body, re.DOTALL)
            if match:
                target_date = match.group(1).strip()
                comment_timestamp = comment.get("created_at")
                comment_url = comment.get("html_url") # Get the URL to the comment
                return target_date, comment_timestamp, comment_url
        
        return None, None, None
    except subprocess.CalledProcessError as e:
        print(f"Error getting comments for {repo}#{issue_number}: {e}")
        if hasattr(e, 'stderr'):
            print(f"stderr: {e.stderr}")
        return None, None, None
    except json.JSONDecodeError:
        print(f"Error decoding comments JSON for {repo}#{issue_number}")
        return None, None, None

def get_sub_issues(
        repo: str, 
        issue_number: str, 
        parent_url: Optional[str] = None, 
        parent_title: Optional[str] = None
        ) -> List[Dict]:
    """Get sub-issues using the GitHub Sub-issues API via gh CLI.
    
    Args:
        repo: Repository in owner/repo format
        issue_number: The issue number
        parent_url: URL of the parent issue
        parent_title: Title of the parent issue
    """
    # Check if gh CLI is available
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI (gh) not found. Please install it: https://cli.github.com/")
    
    # Use gh api to call the sub-issues endpoint with correct headers
    try:
        owner, repository = repo.split('/')
        api_endpoint = f"/repos/{owner}/{repository}/issues/{issue_number}/sub_issues"
        
        # Use gh api command with the correct headers as specified in the GitHub API docs
        cmd = [
            "gh", "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", "X-GitHub-Api-Version: 2022-11-28",
            api_endpoint
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        sub_issues_data = json.loads(result.stdout)
        
        # For each sub-issue, fetch full details to get labels
        sub_issues = []
        for sub_issue in sub_issues_data:
            # Extract repository and issue number from the API response
            sub_repo = sub_issue.get("repository", {}).get("full_name", "")
            if not sub_repo and "repository_url" in sub_issue:
                # Fallback to repository_url if available
                sub_repo = sub_issue.get("repository_url", "").replace("https://api.github.com/repos/", "")
            
            sub_issue_number = str(sub_issue.get("number", ""))
            
            # Only proceed if we have valid information
            if sub_repo and sub_issue_number:
                print(f"  - Found: https://github.com/{sub_repo}/issues/{sub_issue_number}")
                cmd = ["gh", "issue", "view", sub_issue_number, "--repo", sub_repo, "--json", "url,title,labels,number,state,closedAt"]
                sub_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                detailed_sub_issue = json.loads(sub_result.stdout)
                target_date, comment_timestamp, comment_url = get_target_date_from_comments(sub_repo, sub_issue_number)
                detailed_sub_issue["target_date"] = target_date if target_date else "N/A"
                detailed_sub_issue["last_updated_at"] = comment_timestamp if comment_timestamp else "N/A"
                detailed_sub_issue["comment_url"] = comment_url if comment_url else "N/A"
                
                # Add parent issue information
                detailed_sub_issue["parent_url"] = parent_url if parent_url else f"https://github.com/{repo}/issues/{issue_number}"
                detailed_sub_issue["parent_title"] = parent_title if parent_title else f"{repo}#{issue_number}"
                
                sub_issues.append(detailed_sub_issue)
            else:
                print(f"  - Warning: Incomplete sub-issue data: {sub_issue}")
        
        return sub_issues
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting sub-issues for {repo}#{issue_number}: {e}")
        print(f"stderr: {e.stderr}")
        return []

def format_timestamp_with_days_ago(
        timestamp: Optional[str], 
        comment_url: Optional[str], 
        include_days_ago: bool
        ) -> str:
    """
    Format a timestamp string to a markdown link with text 'YYYY-MM-DD (X days ago)'.
    
    Args:
        timestamp: An ISO format timestamp string or None
        comment_url: The URL to the comment
        include_days_ago: Whether to include the 'X days ago' text

    Returns:
        A formatted markdown link or "N/A" if timestamp or comment_url is None
    """
    if not timestamp or timestamp == "N/A" or not comment_url or comment_url == "N/A":
        return "N/A"
    
    try:
        # Parse the ISO format timestamp
        dt = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        # Format the date part
        date_str = dt.strftime("%Y-%m-%d")
        
        # Calculate days ago
        days_text = ""
        if include_days_ago:
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = now - dt
            days_ago = delta.days
            
            if days_ago == 0:
                days_text = "today"
            elif days_ago == 1:
                days_text = "1 day ago"
            else:
                days_text = f"{days_ago} days ago"
            days_text = f" ({days_text})"
        
        # Format as a markdown link
        display_text = f"{date_str}{days_text}"
        return f"[{display_text}]({comment_url})"
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not format timestamp '{timestamp}': {e}")
        return timestamp  # Return the original string if parsing fails

def render_markdown_report(
        issues: List[Dict], 
        show_parent: bool = True, 
        since: Optional[datetime.datetime] = None,
        title: Optional[str] = None
        ) -> str:
    """Render the issues as a markdown report.
    
    Args:
        issues: List of issue dictionaries
        show_parent: Whether to include the parent column
        since: Filter out issues with last update older than this date
        title: Optional title for the report
        
    Returns:
        Markdown formatted report as a string
    """
    result = []
    
    # Add report header with current date
    title = title or "Status Report"
    result.append(f"\n### {title}, {datetime.datetime.now().strftime('%Y-%m-%d')}")
    
    # Create table headers based on whether to show parent column
    if show_parent:
        result.append("\n| status | parent | issue | target date | last update |")
        result.append("|---|:--|:--|:--|:--|")
    else:
        result.append("\n| status | issue | target date | last update |")
        result.append("|---|:--|:--|:--|")
    
    # First, filter issues by last update date if specified
    filtered_issues = []
    for issue in issues:
        if since:
            # Determine which timestamp to use
            is_closed = issue.get("state", "").lower() == "closed"
            closed_at = issue.get("closedAt")
            if is_closed and closed_at:
                timestamp = closed_at
            else:
                timestamp = issue.get("last_updated_at", "N/A")
            
            # Skip if timestamp is before since date or not available
            if timestamp == "N/A":
                continue
            try:
                update_date = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if update_date < since:
                    continue
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse date '{timestamp}': {e}")
                continue  # Skip if we can't parse the date
        filtered_issues.append(issue)
    
    # Sort issues by status, target date, and title
    def get_sort_key(issue):
        # Get status priority (order in STATUS_LABELS dict)
        status = issue.get("status", "inactive")
        status_priority = list(STATUS_LABELS.keys()).index(status) if status in STATUS_LABELS else 999
        
        # Convert target_date to comparable format
        target_date = issue.get("target_date", "9999-99-99")  # Default to a far future date
        # Make sure we can sort "N/A" dates as well
        if target_date == "N/A" or not target_date:
            target_date = "9999-99-99"
        
        # Get issue title for final sort key
        title = issue.get("title", "")
        
        return (status_priority, target_date, title)
    
    # Sort the issues
    sorted_issues = sorted(filtered_issues, key=get_sort_key)
    
    # Group by status and process each issue
    for issue in sorted_issues:
        # Issue details
        url = issue.get("url", "")
        title = issue.get("title", "")
        issue_link = f"[{title}]({url})"
        
        # Status details
        status_name = issue.get("status", "inactive")
        if status_name in STATUS_LABELS:
            status_with_emoji = f"{STATUS_LABELS[status_name]} {status_name}"
        else:
            status_with_emoji = f":question: {status_name}"
        
        # Target date
        target_date = issue.get("target_date", "?")
        
        # Choose which timestamp and URL to use for "last update"
        timestamp = None
        url = None
        is_closed = issue.get("state", "").lower() == "closed"
        closed_at = issue.get("closedAt")
        if is_closed and closed_at:
            # For closed issues, use the closed timestamp
            timestamp = closed_at
            url = issue.get("url", "N/A")  # Link to the issue itself
        else:
            # For open issues, use the comment timestamp
            timestamp = issue.get("last_updated_at", "N/A")
            url = issue.get("comment_url", "N/A")
            
        formatted_timestamp_link = format_timestamp_with_days_ago(timestamp, url, False)
        
        # Parent issue details (if showing)
        row = ""
        if show_parent:
            parent_url = issue.get("parent_url", "")
            parent_title = issue.get("parent_title", "")
            parent_link = f"[{parent_title}]({parent_url})"
            row = f"| {status_with_emoji} | {parent_link} | {issue_link} | {target_date} | {formatted_timestamp_link} |"
        else:
            row = f"| {status_with_emoji} | {issue_link} | {target_date} | {formatted_timestamp_link} |"
        
        result.append(row)
    
    result.append("\n")
    return "\n".join(result)

def generate_report(
        issues: List[str], 
        show_parent: bool = DEFAULT_SHOW_PARENT, 
        since: Optional[datetime.datetime] = None,
        output_file: Optional[str] = None
        ) -> None:
    """Generate a report of all sub-issues with their labels using gh CLI.
    
    Args:
        issues: List of GitHub issue URLs
        show_parent: Whether to include parent column in the report
        since: Minimum date for filtering issues by last update
        output_file: Optional file path to write the markdown output instead of printing to console
    """
    # Check if gh CLI is available and authenticated
    if not shutil.which("gh"):
        print("Error: GitHub CLI (gh) not found.")
        print("Please install it from: https://cli.github.com/")
        return
    
    try:
        # Quick check to see if gh is authenticated
        subprocess.run(["gh", "auth", "status"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("Error: Not authenticated with GitHub CLI.")
        print("Please run: gh auth login")
        return
    
    all_sub_issues = []
    parent_title = None
    parent_url = None
    for issue_url in issues:
        try:
            repo, issue_number = extract_repo_and_issue_number(issue_url)
            print(f"Processing {issue_url}...")
            
            # Fetch parent issue details
            parent_url = issue_url
            parent_title = f"{repo}#{issue_number}"
            try:
                cmd = ["gh", "issue", "view", issue_number, "--repo", repo, "--json", "url,title"]
                parent_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                parent_details = json.loads(parent_result.stdout)
                parent_title = parent_details.get("title", f"{repo}#{issue_number}")
                parent_url = parent_details.get("url", issue_url) # use this in case there was a redirect.
            except Exception as e:
                print(f"  Warning: Could not fetch details for {issue_url}")
                continue
            
            sub_issues = get_sub_issues(repo, issue_number, parent_url, parent_title)
            all_sub_issues.extend(sub_issues)
            
            print(f"  Found {len(sub_issues)} sub-issues")
        except Exception as e:
            print(f"Error processing {issue_url}: {e}")
            # More detailed error output for debugging
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
            if isinstance(e, subprocess.CalledProcessError) and hasattr(e, 'stderr'):
                print(f"stderr: {e.stderr}")
            print(traceback.format_exc())
    
    if not all_sub_issues:
        print("  No sub-issues found.")
        return
    
    # Check the labels to determine the status of each issue
    # Check these in order in case there are multiple "status" labels -- we pick the first one.
    for issue in all_sub_issues:
        status = "inactive"
        label_names = [label.get("name", "").lower() for label in issue.get("labels", [])]
        for sl in STATUS_LABELS.keys():
            if sl in label_names:
                status = sl
                break
        issue["status"] = status

    # Generate the markdown report
    custom_title = None 
    if len(issues) == 1:
        custom_title = f"[{parent_title}]({parent_url})"

    markdown_report = render_markdown_report(
        issues=all_sub_issues, 
        show_parent=show_parent, 
        since=since,
        title = custom_title
    )
    
    # Either write to file or print to console
    if output_file:
        try:
            # Check if the file exists to decide on mode
            file_exists = os.path.exists(output_file)
            # Use append mode if file exists and we're running in separate reports mode
            mode = 'a' if file_exists else 'w'
            
            with open(output_file, mode) as f:
                # Add new lines if appending
                if mode == 'a':
                    f.write("\n\n\n\n")
                f.write(markdown_report)
            
        except IOError as e:
            print(f"Error writing to file {output_file}: {e}")
            print(markdown_report)  # Fallback to console output
    else:
        print(markdown_report)

if __name__ == "__main__":
    try:
        # Check if gh CLI is installed
        if not shutil.which("gh"):
            raise RuntimeError("GitHub CLI (gh) not found. Please install it: https://cli.github.com/")

        # Set up argument parser
        parser = argparse.ArgumentParser(description="Generate a report of GitHub sub-issues")
        parser.add_argument("issues", nargs="+", help="The 'parent' GitHub issue URLs to search for sub-issues")
        parser.add_argument("--include-parent", action="store_true", help="Include parent column in the report")
        parser.add_argument("--since", type=str, help="Only include issues updated on or after this date (YYYY-MM-DD)")
        parser.add_argument("--output-file", "-o", type=str, help="Write the markdown report to this file instead of standard output")
        parser.add_argument("--individual", "-i", action="store_true", help="Generate a separate report for each provided issue")
        
        args = parser.parse_args()

        # Parse the since date if provided
        since = None
        if args.since:
            try:
                since = datetime.datetime.fromisoformat(args.since)
                print(f"Filtering issues updated after {since}")
            except ValueError:
                print(f"Warning: Invalid date format '{args.since}'. Expected YYYY-MM-DD.")
                sys.exit(1)

        # If output file exists and we're about to generate separate reports, remove it first
        if args.output_file and os.path.exists(args.output_file):
            try:
                os.remove(args.output_file)
                print(f"Removed existing file: {args.output_file}")
            except OSError as e:
                print(f"Warning: Could not remove existing file {args.output_file}: {e}")
            

        # Check if the separate reports mode is enabled
        if args.individual:
            for issue_url in args.issues:
                generate_report(
                    issues=[issue_url],  # Pass a single issue as a list
                    show_parent=args.include_parent,
                    since=since,
                    output_file=args.output_file
                )
        else:
            # Generate a combined report with all issues (default behavior)
            generate_report(
                issues=args.issues,
                show_parent=args.include_parent,
                since=since,
                output_file=args.output_file
            )

    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        sys.exit(0)

