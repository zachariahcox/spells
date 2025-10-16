import argparse
import shutil
import sys
import subprocess
from typing import List

def run_gh_command(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run a GitHub CLI command and return the completed process."""
    assert cmd
    assert isinstance(cmd, list)
    assert cmd and cmd[0] == "gh"

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result

if __name__ == "__main__":
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI (gh) not found. Please install it: https://cli.github.com/")
    parser = argparse.ArgumentParser(description="Generate a status report for GitHub issues (and optional sub-issues)")
    parser.add_argument("--stdin", "-s", action="store_true", help="Read issue URLs from stdin (one per line)")
    parser.add_argument("--add", nargs="+", help="Add a label to the specified issues")
    parser.add_argument("--remove", nargs="+", help="Remove a label from the specified issues")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without executing them")
    args = parser.parse_args()

    issue_urls = []
    if args.stdin or (not issue_urls and not sys.stdin.isatty()):
        for line in sys.stdin:
            url = line.strip()
            if url:
                issue_urls.append(url)
    if not issue_urls:
        parser.print_help()
        sys.exit(1)

    # organize by repo
    issues_by_repo = {}
    for url in issue_urls:
        # Extract the repository and issue number from the URL
        parts = url.split('/')
        if len(parts) < 5:
            continue
        owner = parts[3]
        repo = parts[4]
        issue_number = parts[6]
        nwo = f"{owner}/{repo}"
        if nwo not in issues_by_repo:
            issues_by_repo[nwo] = []
        issues_by_repo[nwo].append(issue_number)

    # Process add and remove label actions
    for nwo, issue_numbers in issues_by_repo.items():
        if args.add:
            for label in args.add:
                for issue_number in issue_numbers:
                    cmd = ["gh", "issue", "edit", issue_number, "--repo", nwo, "--add-label", label]
                    if args.dry_run:
                        print(" ".join(cmd))
                    else:
                        run_gh_command(cmd)

        if args.remove:
            for label in args.remove:
                for issue_number in issue_numbers:
                    cmd = ["gh", "issue", "edit", issue_number, "--repo", nwo, "--remove-label", label]
                    if args.dry_run:
                        print(" ".join(cmd))
                    else:
                        run_gh_command(cmd)