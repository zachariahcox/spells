"""
Generate status reports for GitHub issues (optionally including their sub-issues) using the GitHub CLI.

Features:
  - Fetch parent issues and (optionally) their sub-issues via the GitHub Sub-issues API.
  - Derive a status from labels (done, on track, at risk, high risk, inactive) and decorate with emojis.
  - Extract a target date embedded in an HTML comment block within issue comments.
  - Include last update timestamps (either closed date or latest target-date comment) with convenient formatting.
  - Filter issues by a minimum last-update date.
  - Emit a combined report for multiple roots or individual reports per root.
  - Output to stdout or append/write to a specified markdown file.

Usage:
    python report.py [options] <issue_urls>

Options:
    --include-parent
        When including sub-issues, add a dedicated parent column to the table.
    --include-subissues
        Include sub-issues of each supplied root issue. If omitted, only root issues are reported.
    --since <date>
        Only include issues updated on or after this date (YYYY-MM-DD).
    --output-file <file>, -o <file>
        Write (or append) the markdown report to this file instead of standard output.
    --individual, -i
        Generate a separate report section (or file append) for each provided issue URL.
    --stdin, -s
        Read issue URLs from standard input (one per line). Useful for piping.
    --verbose, -v
        Enable verbose / debug logging.
    --quiet, -q
        Suppress non-essential output (only errors).

Examples:
    python report.py --include-parent --include-subissues --since 2025-01-01 --output-file status.md https://github.com/org/repo/issues/123
    cat issues.txt | python report.py --stdin --include-subissues --include-parent -o aggregated.md

Notes:
  - You must have the GitHub CLI installed and authenticated with sufficient scopes for issues & sub-issues.
  - Run: gh auth login   (or)   gh auth refresh -s project
"""
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
import logging

# Set up logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)  # Default to INFO level

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

STATUS_MAPPING = {
    "🎉 Done": "done",
    "🚧 Executing": "on track",
    "🎯 Prioritized": "inactive",
}

def run_gh_command(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run a GitHub CLI command and return the completed process."""
    logger.debug(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    logger.debug(f"Command completed with exit code: {result.returncode}")
    return result


def get_status(issue: Dict, comment_status) -> str:
    if issue.get("state", "").lower() == "closed":
        return "done" # apparently!

    if comment_status:
        return comment_status

    label_names = [label.get("name", "").lower() for label in issue.get("labels", [])]
    for s in STATUS_LABELS.keys():
        if s in label_names:
            return s

    return "inactive"

def log_json(data, message=None):
    """Helper function to log JSON data during debugging"""
    if logger.level <= logging.DEBUG:
        if message:
            logger.debug(message)
        try:
            logger.debug(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug(f"Could not format JSON: {e}")
            logger.debug(str(data))

def extract_repo_and_issue_number(issue_url: str) -> Tuple[str, str]:
    """Extract repository name and issue number from a GitHub issue URL."""
    match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', issue_url)
    if match:
        repo = match.group(1)
        issue_number = match.group(2)
        return repo, issue_number
    raise ValueError(f"Invalid GitHub issue URL: {issue_url}")

def get_state_from_comments(
        repo: str,
        issue_number: str
        ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Extract state from issue comments, searching from newest to oldest.

    Returns:
        A tuple (target_date, comment_created_at, comment_url, status) where:
        - target_date: The extracted target date or None if not found
        - comment_created_at: The timestamp of the comment containing the target date or None if not found
        - comment_url: The URL of the comment containing the target date or None if not found
    """
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
    result = run_gh_command(cmd)
    # Paginated results might come as arrays on separate lines
    try:
        content = result.stdout
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
        logger.error(f"Error parsing comments JSON: {e}")
        comments = []

    # prefer the most recent commits
    comments.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    target_date_pattern = r'<!-- data key="target_date" start -->\s*(.*?)\s*<!-- data end -->'
    target_date = None
    comment_timestamp = None
    comment_url = None

    logger.debug(f"Searching for target date in {len(comments)} comments for {repo}#{issue_number}")
    for comment in comments:
        body = comment.get("body", "")
        logger.debug(f"Checking comment from {comment.get('created_at', 'unknown date')}")
        match = re.search(target_date_pattern, body, re.DOTALL)
        if match:
            target_date = match.group(1).strip()
            comment_timestamp = comment.get("created_at")
            comment_url = comment.get("html_url")
            break

    # check for status overrides
    status_pattern = r'<!-- data key="status" start -->\s*(.*?)\s*<!-- data end -->'
    status = None
    for comment in comments:
        body = comment.get("body", "")
        match = re.search(status_pattern, body, re.DOTALL)
        if match:
            status = match.group(1).strip()
            comment_timestamp = comment.get("created_at")
            comment_url = comment.get("html_url")
            break

    # look up mapped comment status
    if status:
        status = STATUS_MAPPING.get(status)

    return target_date, comment_timestamp, comment_url, status


def get_issue_details(
        repo: str,
        issue_number: str,
        parent_url: Optional[str] = None,
        parent_title: Optional[str] = None,
        ) -> Optional[Dict]:
    """Get issue details using gh CLI."""
    if not repo or not issue_number:
        return None
    logger.info(f"  - Found: https://github.com/{repo}/issues/{issue_number}")
    cmd = ["gh", "issue", "view", issue_number, "--repo", repo, "--json", "url,title,labels,number,state,closedAt"]
    sub_result = run_gh_command(cmd)

    detailed_issue = json.loads(sub_result.stdout)
    log_json(detailed_issue, f"Detailed sub-issue data for {repo}#{issue_number}:")
    target_date, comment_timestamp, comment_url, comment_status = get_state_from_comments(repo, issue_number)
    detailed_issue["target_date"] = target_date if target_date else "N/A"
    detailed_issue["last_updated_at"] = comment_timestamp if comment_timestamp else "N/A"
    detailed_issue["comment_url"] = comment_url if comment_url else "N/A"
    detailed_issue["parent_url"] = parent_url if parent_url else f"https://github.com/{repo}/issues/{issue_number}"
    detailed_issue["parent_title"] = parent_title if parent_title else f"{repo}#{issue_number}"
    detailed_issue["status"] = get_status(detailed_issue, comment_status)
    return detailed_issue

def get_sub_issues(
        parent_repo: str,
        parent_issue_number: str,
        parent_url: Optional[str] = None,
        parent_title: Optional[str] = None
        ) -> List[Dict]:
    """Get sub-issues using the GitHub Sub-issues API via gh CLI."""
    owner, repository = parent_repo.split('/')
    api_endpoint = f"/repos/{owner}/{repository}/issues/{parent_issue_number}/sub_issues"
    cmd = [
        "gh", "api",
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28",
        api_endpoint
    ]
    result = run_gh_command(cmd)
    sub_issues_data = json.loads(result.stdout)
    log_json(sub_issues_data, f"Sub-issues data for {parent_repo}#{parent_issue_number}:")
    sub_issues = []
    for sub_issue in sub_issues_data:
        sub_repo = sub_issue.get("repository", {}).get("full_name", "")
        if not sub_repo and "repository_url" in sub_issue:
            sub_repo = sub_issue.get("repository_url", "").replace("https://api.github.com/repos/", "")
        sub_issue_number = str(sub_issue.get("number", ""))
        detailed_sub_issue = get_issue_details(sub_repo, sub_issue_number, parent_url, parent_title)
        if detailed_sub_issue:
            sub_issues.append(detailed_sub_issue)
    return sub_issues

def format_timestamp_with_days_ago(
        timestamp: Optional[str],
        comment_url: Optional[str],
        include_days_ago: bool
        ) -> str:
    """Format a timestamp string as a markdown link with optional relative day text."""
    if not timestamp or timestamp == "N/A" or not comment_url or comment_url == "N/A":
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
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
        display_text = f"{date_str}{days_text}"
        return f"[{display_text}]({comment_url})"
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
    title = title or "Status Report"
    result.append(f"\n### {title}, {datetime.datetime.now().strftime('%Y-%m-%d')}")
    if show_parent:
        result.append("\n| status | parent | issue | target date | last update |")
        result.append("|---|:--|:--|:--|:--|")
    else:
        result.append("\n| status | issue | target date | last update |")
        result.append("|---|:--|:--|:--|")
    filtered_issues = []
    for issue in issues:
        if since:
            is_closed = issue.get("state", "").lower() == "closed"
            closed_at = issue.get("closedAt")
            timestamp = closed_at if (is_closed and closed_at) else issue.get("last_updated_at", "N/A")
            if timestamp == "N/A":
                continue
            try:
                update_date = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if update_date < since:
                    continue
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date '{timestamp}': {e}")
                continue
        filtered_issues.append(issue)

    def get_sort_key(issue):
        status = issue.get("status", "inactive")
        status_priority = list(STATUS_LABELS.keys()).index(status) if status in STATUS_LABELS else 999
        target_date = issue.get("target_date", "9999-99-99")
        if target_date == "N/A":
            target_date = "9999-99-99"
        last_update = issue.get("last_updated_at", "9999-99-99")
        title_inner = issue.get("title", "")
        return (status_priority, target_date, last_update, title_inner)

    for issue in sorted(filtered_issues, key=get_sort_key):
        url = issue.get("url", "")
        title_text = issue.get("title", "")
        issue_link = f"[{title_text}]({url})"
        status_name = issue.get("status", "inactive")
        status_with_emoji = f"{STATUS_LABELS[status_name]} {status_name}" if status_name in STATUS_LABELS else f":question: {status_name}"
        target_date = issue.get("target_date", "?")
        is_closed = issue.get("state", "").lower() == "closed"
        closed_at = issue.get("closedAt")
        timestamp = closed_at if (is_closed and closed_at) else issue.get("last_updated_at", "N/A")
        link_url = issue.get("url", "N/A") if (is_closed and closed_at) else issue.get("comment_url", "N/A")
        formatted_timestamp_link = format_timestamp_with_days_ago(timestamp, link_url, False)
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
        issue_urls: List[str],
        show_parent: bool = DEFAULT_SHOW_PARENT,
        show_subissues: bool = True,
        since: Optional[datetime.datetime] = None,
        output_file: Optional[str] = None
        ) -> None:
    """Generate a report of all (sub-)issues with their status and metadata."""
    if not shutil.which("gh"):
        logger.error("GitHub CLI (gh) not found.")
        logger.error("Please install it from: https://cli.github.com/")
        return
    try:
        subprocess.run(["gh", "auth", "status"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        logger.error("Not authenticated with GitHub CLI. Run: gh auth login")
        return
    root_issues: List[Dict] = []
    all_sub_issues: List[Dict] = []
    parent_title = None
    parent_url = None
    for issue_url in issue_urls:
        logger.info(f"Processing {issue_url}...")
        repo, issue_number = extract_repo_and_issue_number(issue_url)
        parent_url = issue_url
        parent_title = f"{repo}#{issue_number}"
        detailed_issue = get_issue_details(repo, issue_number)
        if detailed_issue:
            root_issues.append(detailed_issue)
            parent_title = detailed_issue.get("title", parent_title)
            parent_url = detailed_issue.get("url", parent_url)
        if show_subissues:
            sub_issues = get_sub_issues(repo, issue_number, parent_url, parent_title)
            all_sub_issues.extend(sub_issues)
            logger.info(f"  Found {len(sub_issues)} sub-issues")

    custom_title = None
    if len(issue_urls) == 1:
        custom_title = f"[{parent_title}]({parent_url})"
    if show_subissues:
        markdown_report = render_markdown_report(
            issues=all_sub_issues,
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
        except IOError as e:  # noqa: PERF203
            logger.error(f"Error writing to file {output_file}: {e}")
            print(markdown_report)
    else:
        print(markdown_report)

if __name__ == "__main__":
    try:
        if not shutil.which("gh"):
            raise RuntimeError("GitHub CLI (gh) not found. Please install it: https://cli.github.com/")
        parser = argparse.ArgumentParser(description="Generate a status report for GitHub issues (and optional sub-issues)")
        parser.add_argument("issues", nargs="*", help="Root GitHub issue URLs to render")
        parser.add_argument("--include-parent", action="store_true", help="When showing sub-issues, include a parent column")
        parser.add_argument("--include-subissues", action="store_true", help="Include sub-issues in the report output")
        parser.add_argument("--since", type=str, help="Only include issues updated on or after this date (YYYY-MM-DD)")
        parser.add_argument("--output-file", "-o", type=str, help="Write / append the markdown report to this file")
        parser.add_argument("--individual", "-i", action="store_true", help="Generate a separate report section for each parent issue")
        parser.add_argument("--stdin", "-s", action="store_true", help="Read issue URLs from stdin (one per line)")
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
        parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output")
        args = parser.parse_args()
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        elif args.quiet:
            logger.setLevel(logging.ERROR)
        else:
            logger.setLevel(logging.WARNING)
        issue_urls = args.issues.copy() if args.issues else []
        if args.stdin or (not issue_urls and not sys.stdin.isatty()):
            logger.info("Reading issue URLs from stdin...")
            for line in sys.stdin:
                url = line.strip()
                if url:
                    issue_urls.append(url)
        if not issue_urls:
            parser.print_help()
            logger.error("No issue URLs provided. Provide them as arguments or pipe with --stdin.")
            sys.exit(1)
        logger.info(f"Processing {len(issue_urls)} issues...")
        since = None
        if args.since:
            try:
                since = datetime.datetime.fromisoformat(args.since)
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
        if args.individual:
            for issue_url in issue_urls:
                generate_report(
                    issue_urls=[issue_url],
                    show_parent=args.include_parent,
                    show_subissues=args.include_subissues,
                    since=since,
                    output_file=args.output_file
                )
        else:
            generate_report(
                issue_urls=issue_urls,
                show_parent=args.include_parent,
                show_subissues=args.include_subissues,
                since=since,
                output_file=args.output_file
            )
    except KeyboardInterrupt:
        logger.warning("\nOperation canceled by user.")
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Unexpected error: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)
