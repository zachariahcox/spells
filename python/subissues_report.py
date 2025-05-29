# This script uses the GitHub CLI to fetch sub-issues of a given list of issues.
import json
import re
import subprocess
from typing import List, Dict, Tuple, Optional
import shutil
import sys


# howie labels
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

def get_target_date_from_comments(repo: str, issue_number: str) -> Optional[str]:
    """Extract Target Date from the most recent comment of an issue."""
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
        
        # Look for Target Date in the HTML comments format - only in the most recent comment
        target_date_pattern = r'<!-- data key="target_date" start -->\s*(.*?)\s*<!-- data end -->'
        
        # Check only the most recent comment if available
        if comments:
            body = comments[0].get("body", "")
            match = re.search(target_date_pattern, body, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error getting comments for {repo}#{issue_number}: {e}")
        if hasattr(e, 'stderr'):
            print(f"stderr: {e.stderr}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding comments JSON for {repo}#{issue_number}")
        return None

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
                detailed_sub_issue["target_date"] = get_target_date_from_comments(sub_repo, sub_issue_number)
                
                sub_issues.append(detailed_sub_issue)
            else:
                print(f"  - Warning: Incomplete sub-issue data: {sub_issue}")
        
        return sub_issues
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting sub-issues for {repo}#{issue_number}: {e}")
        print(f"stderr: {e.stderr}")
        return []

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
    print("\n| status | issue | target date |")
    print("|---|:--|:--|")
    
    for status in status_labels.keys():    
        for issue in all_sub_issues:
            if issue.get("status") != status:
                continue # super dumb way to do this lol

            url = issue.get("url", "N/A")
            title = issue.get("title", "N/A")
            issue_link = f"[{title}]({url})"

            status_name = issue.get("status")
            status_with_emoji = f"{status_labels[status_name]} {status_name}"
            
            # Get target date
            target_date = issue.get("target_date", "?")
            
            # Print the row
            print(f"| {status_with_emoji} | {issue_link} | {target_date} |")

if __name__ == "__main__":
    try:
        # parse list of issues from command line arguments
        if len(sys.argv) > 1:
            issues = sys.argv[1:]
        else:
            print("Usage: python subissues_report.py <issue_url_1> <issue_url_2> ...")
            sys.exit(1)


        generate_report(issues)
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        sys.exit(0)

