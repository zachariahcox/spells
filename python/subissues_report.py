# This script uses the GitHub CLI to fetch sub-issues of a given list of issues.
import json
import re
import subprocess
from typing import List, Dict, Tuple, Optional
import shutil
import sys
import datetime


# standard status labels and some emojis for display
status_labels = {
    "done": ":purple_circle:", 
    "on track": ":green_circle:", 
    "inactive": ":white_circle:", 
    "at risk": ":yellow_circle:", 
    "high risk": ":red_circle:", 
}

def extract_repo_and_issue_number(issue_url: str) -> Tuple[str, str]:
    """Extract repository name and issue number from a GitHub issue URL."""
    match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', issue_url)
    if match:
        repo = match.group(1)
        issue_number = match.group(2)
        return repo, issue_number
    raise ValueError(f"Invalid GitHub issue URL: {issue_url}")

def get_target_date_from_comments(repo: str, issue_number: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
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

def get_sub_issues(repo: str, issue_number: str) -> List[Dict]:
    """Get sub-issues using the GitHub Sub-issues API via gh CLI."""
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
        
        print(f"  Running: {' '.join(cmd)}")
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
                print(f"  - Found sub-issue: {sub_repo}#{sub_issue_number}")
                cmd = ["gh", "issue", "view", sub_issue_number, "--repo", sub_repo, "--json", "url,title,labels,number,state"]
                sub_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                detailed_sub_issue = json.loads(sub_result.stdout)
                target_date, comment_timestamp, comment_url = get_target_date_from_comments(sub_repo, sub_issue_number)
                detailed_sub_issue["target_date"] = target_date if target_date else "N/A"
                detailed_sub_issue["last_updated_at"] = comment_timestamp if comment_timestamp else "N/A"
                detailed_sub_issue["comment_url"] = comment_url if comment_url else "N/A"
                
                sub_issues.append(detailed_sub_issue)
            else:
                print(f"  - Warning: Incomplete sub-issue data: {sub_issue}")
        
        return sub_issues
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting sub-issues for {repo}#{issue_number}: {e}")
        print(f"stderr: {e.stderr}")
        return []

def format_timestamp(timestamp: str) -> str:
    """Format the timestamp to show time ago."""
    if not timestamp:
        return "N/A"
    try:
        # Convert the timestamp to a datetime object
        dt = datetime.datetime.fromisoformat(timestamp[:-1])
        # Calculate the difference between now and the timestamp
        now = datetime.datetime.now()
        diff = now - dt
        # Calculate days, hours, and minutes
        days, seconds = diff.days, diff.seconds
        hours, minutes = divmod(seconds, 3600)
        minutes //= 60
        # Format the time ago string
        time_ago = []
        if days > 0:
            time_ago.append(f"{days}d")
        if hours > 0:
            time_ago.append(f"{hours}h")
        if minutes > 0:
            time_ago.append(f"{minutes}m")
        return " ".join(time_ago)
    except Exception as e:
        print(f"Error formatting timestamp {timestamp}: {e}")
        return timestamp

def format_timestamp_with_days_ago(timestamp: Optional[str], comment_url: Optional[str]) -> str:
    """Format a timestamp string to a markdown link with text 'YYYY-MM-DD (X days ago)'.
    
    Args:
        timestamp: An ISO format timestamp string or None
        comment_url: The URL to the comment
        
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
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = now - dt
        days_ago = delta.days
        
        if days_ago == 0:
            days_text = "today"
        elif days_ago == 1:
            days_text = "1 day ago"
        else:
            days_text = f"{days_ago} days ago"
        
        # Format as a markdown link
        display_text = f"{date_str} ({days_text})"
        return f"[{display_text}]({comment_url})"
    except (ValueError, TypeError):
        return timestamp  # Return the original string if parsing fails

def generate_report(issues: List[str]) -> None:
    """Generate a report of all sub-issues with their labels using gh CLI."""
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
    
    for issue_url in issues:
        try:
            repo, issue_number = extract_repo_and_issue_number(issue_url)
            print(f"Processing {repo} issue #{issue_number}...")
            
            sub_issues = get_sub_issues(repo, issue_number)
            all_sub_issues.extend(sub_issues)
            
            print(f"  Found {len(sub_issues)} sub-issues for {issue_url}")
        except Exception as e:
            print(f"Error processing {issue_url}: {e}")
            # More detailed error output for debugging
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
            if isinstance(e, subprocess.CalledProcessError) and hasattr(e, 'stderr'):
                print(f"stderr: {e.stderr}")
    
    if not all_sub_issues:
        print("  No sub-issues found.")
        sys.exit(1)
    
    for issue in all_sub_issues:
        # Format status column - find labels that match our status_labels
        status = ":question: unknown"
        for label in issue.get("labels", []):
            label_name = label.get("name", "").lower()
            if label_name in status_labels:
                status = label_name
                break
        issue["status"] = status

    # Print report in markdown format
    print("\n# Sub-Issues Report")
    print("\n| status | issue | target date | last update |")
    print("|---|:--|:--|:--|")
    
    for status in status_labels.keys():    
        for issue in all_sub_issues:
            if issue.get("status") != status:
                continue # super dumb way to do this lol

            url = issue.get("url", "")
            title = issue.get("title", "")
            issue_link = f"[{title}]({url})"

            status_name = issue.get("status")
            status_with_emoji = f"{status_labels[status_name]} {status_name}"
            
            # Get target date
            target_date = issue.get("target_date", "?")
            
            # Get and format last updated timestamp with a link to the comment
            last_updated_timestamp = issue.get("last_updated_at", "N/A")
            comment_url = issue.get("comment_url", "N/A")
            formatted_timestamp_link = format_timestamp_with_days_ago(last_updated_timestamp, comment_url)
            
            # Print the row
            print(f"| {status_with_emoji} | {issue_link} | {target_date} | {formatted_timestamp_link} |")

if __name__ == "__main__":
    try:
        # parse list of issues from command line arguments
        if len(sys.argv) > 1:
            issues = sys.argv[1:]
        else:
            print(f"Usage: python {__file__} <issue_url_1> <issue_url_2> ...")
            sys.exit(1)


        generate_report(issues)
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        sys.exit(0)

