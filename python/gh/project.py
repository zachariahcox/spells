"""
The script produces lists of GitHub issues referenced by GitHub projects.
The projects API has key limitations on query lengths.
Many operations require multiple queries and offline processing.

You'll need to have the GitHub CLI installed and authenticated with the `project` scope.
Usage:
    python project.py <project_url> [--field NAME VALUE] [--output FORMAT] [--verbose] [--quiet] [--subissues] [--title]
"""
import subprocess
import json
import re
import shutil
import sys
import argparse
import logging
from typing import List, Dict, Optional, Tuple

# Setup logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
handler.setLevel(logging.DEBUG)

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

def create_project_query_template(
    entity_type: str, 
    entity_identifier: str, 
    project_number: str
) -> str:
    """
    Create a GraphQL query template for a GitHub project.
    
    Args:
        entity_type: The type of entity (organization, user, or repository)
        entity_identifier: The identifier(s) for the entity - org name, user login, or owner/repo pair
        project_number: The project number
        
    Returns:
        A formatted GraphQL query string
    """
    # For repository type, we need to split the identifier into owner and repo
    entity_params = ""
    if entity_type == "repository":
        owner, repo = entity_identifier.split('/')
        entity_params = f'(owner: "{owner}", name: "{repo}")'
    elif entity_type == "organization" or entity_type == "user":
        entity_params = f'(login: "{entity_identifier}")'
    
    # Build the GraphQL query using the appropriate entity type
    return f"""
    query {{
        {entity_type}{entity_params} {{
        projectV2(number: {project_number}) {{
            fields(first: 20) {{
                nodes {{
                    ... on ProjectV2Field {{
                        id
                        name
                    }}
                    ... on ProjectV2IterationField {{
                        id
                        name
                    }}
                    ... on ProjectV2SingleSelectField {{
                        id
                        name
                        options {{
                            id
                            name
                        }}
                    }}
                }}
            }}
            items(first: 100) {{
            pageInfo {{
                hasNextPage
                endCursor
            }}
            nodes {{
                id
                fieldValues(first: 20) {{
                    nodes {{
                        ... on ProjectV2ItemFieldTextValue {{
                            text
                            field {{ ... on ProjectV2Field {{ name id }} }}
                        }}
                        ... on ProjectV2ItemFieldDateValue {{
                            date
                            field {{ ... on ProjectV2Field {{ name id }} }}
                        }}
                        ... on ProjectV2ItemFieldSingleSelectValue {{
                            name
                            field {{ ... on ProjectV2SingleSelectField {{ name id }} }}
                        }}
                        ... on ProjectV2ItemFieldNumberValue {{
                            number
                            field {{ ... on ProjectV2Field {{ name id }} }}
                        }}
                    }}
                }}
                content {{
                ... on Issue {{
                    url
                    title
                    state
                    labels(first: 10) {{
                      nodes {{
                        name
                        color
                      }}
                    }}
                    __typename
                }}
                }}
            }}
            }}
        }}
        }}
    }}
    """

def get_issues(
    project_url: str, 
    field_values: dict[str, str] | None = None,
    negative_field_values: List[Tuple[str, str]] | None = None
) -> list[Dict[str, str]]:
    """Search for GitHub issues using a query string and filter to only issues in the specified project.
    
    Args:
        project_url: The URL of the GitHub project to filter issues by. Project can contain issues from multiple repos.
        field_values: Optional dictionary of project field values to filter by {field_name: field_value}
        negative_field_values: Optional list of tuples for project field values to exclude [(field_name, field_value)]
    Returns:
        List of GitHub issue URLs belonging to the specified project
    """
    # First check if a project URL is provided
    if not project_url:
        # When no project URL is provided, raise an error
        logger.error("Project URL must be provided to filter issues by project")
        raise ValueError("Project URL must be provided to filter issues by project")
    
    check_gh_auth_scopes()

    try:    
        # Extract project owner, repo, and number from the URL
        # Format could be:
        # - https://github.com/orgs/{org}/projects/{number}
        # - https://github.com/users/{user}/projects/{number}
        # - https://github.com/{owner}/{repo}/projects/{number}
        
        org_match = re.search(r'github\.com/orgs/([^/]+)/projects/(\d+)', project_url)
        user_match = re.search(r'github\.com/users/([^/]+)/projects/(\d+)', project_url)
        repo_match = re.search(r'github\.com/([^/]+)/([^/]+)/projects/(\d+)', project_url)
        
        # Construct GraphQL query based on the project URL type
        graphql_query = ""
        
        if org_match:
            org = org_match.group(1)
            project_number = org_match.group(2)
            logger.debug(f"Fetching issues from organization project: {org}/projects/{project_number}")
            
            # GraphQL query for organization project
            graphql_query = create_project_query_template("organization", org, project_number)
        elif user_match:
            user = user_match.group(1)
            project_number = user_match.group(2)
            logger.debug(f"Fetching issues from user project: {user}/projects/{project_number}")
            
            # GraphQL query for user project
            graphql_query = create_project_query_template("user", user, project_number)
        elif repo_match:
            owner = repo_match.group(1)
            repo = repo_match.group(2)
            project_number = repo_match.group(3)
            logger.debug(f"Fetching issues from repository project: {owner}/{repo}/projects/{project_number}")
            
            # GraphQL query for repository project
            graphql_query = create_project_query_template("repository", f"{owner}/{repo}", project_number)
        else:
            logger.error(f"Unrecognized project URL format: {project_url}")
            return []
        
        # Run the GraphQL query using GitHub CLI with pagination
        all_data = {"data": {}}
        has_next_page = True
        end_cursor = None

        # Determine the node name for navigating the response structure
        node_name = "unknown"
        if org_match:
            node_name = "organization"
        elif user_match:
            node_name = "user"
        elif repo_match:
            node_name = "repository"
        
        while has_next_page:
            # Add pagination parameters
            paginated_query = graphql_query
            if end_cursor:
                # Replace the items first argument to include the after cursor
                paginated_query = paginated_query.replace(
                    'items(first: 100)', 
                    f'items(first: 100, after: "{end_cursor}")'
                )
            
            cmd = [
                "gh", "api", "graphql",
                "-f", f"query={paginated_query}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            page_data = json.loads(result.stdout)
            
            # For the first page, initialize the data structure
            if not all_data["data"]:
                all_data["data"] = page_data["data"]
            else:
                source_path = ["data", node_name, "projectV2", "items", "nodes"]
                target_path = all_data["data"][node_name]["projectV2"]["items"]["nodes"]

                # Get the nodes from the current page
                nodes = page_data
                for key in source_path:
                    nodes = nodes.get(key, {})
                
                # Append the nodes to the accumulated data
                if isinstance(nodes, list):
                    target_path.extend(nodes)
            
            # Check if there are more pages
            page_info = page_data.get("data", {}).get(node_name, {}).get("projectV2", {}).get("items", {}).get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor")
            
            if has_next_page:
                logger.debug(f"Fetching next page of items with cursor: {end_cursor}")
        
        # Use the accumulated data for further processing
        data = all_data

        # Get project fields structure
        project_data = data.get("data", {}).get(node_name, {}).get("projectV2", {})
        
        # Build lookup dictionary for fields by name
        fields = project_data.get("fields", {}).get("nodes", [])
        field_dict = {}
        for field in fields:
            if "name" in field:
                field_dict[field["name"]] = field
        
        # Extract issue URLs and other details
        issue_details = []
        items = project_data.get("items", {}).get("nodes", [])
        for item in items:
            content = item.get("content", {})
            item_field_values = {}
            
            # Extract field values for this item
            if "fieldValues" in item and "nodes" in item["fieldValues"]:
                for fv in item["fieldValues"]["nodes"]:
                    if "field" in fv and "name" in fv["field"]:
                        field_name = fv["field"]["name"]
                        
                        # Extract the value based on field type
                        if "text" in fv:
                            item_field_values[field_name] = fv["text"]
                        elif "date" in fv:
                            item_field_values[field_name] = fv["date"]
                        elif "name" in fv:  # Single select field
                            item_field_values[field_name] = fv["name"]
                        elif "number" in fv:
                            item_field_values[field_name] = fv["number"]
            
            # Apply the field filters 
            should_skip = False
            if field_values:
                for field_name, expected_value in field_values.items():
                    if field_name not in item_field_values or item_field_values[field_name] != expected_value:
                        should_skip = True
                        break
            if negative_field_values:
                for field_name, excluded_value in negative_field_values:
                    if field_name in item_field_values and item_field_values[field_name] == excluded_value:
                        should_skip = True
                        break
            if should_skip:
                continue
                    
            if content:
                # Extract label information
                labels = []
                if "labels" in content and "nodes" in content["labels"]:
                    for label_node in content["labels"]["nodes"]:
                        if "name" in label_node:
                            labels.append({
                                "name": label_node["name"],
                                "color": label_node.get("color", "")
                            })
                
                # Create a detailed issue object
                issue_details.append({
                    "url": content["url"],
                    "title": content.get("title", "No title"),
                    "state": content.get("state", "No state"),
                    "labels": labels,
                    "type": content.get("__typename", "No type"),
                    "field_values": item_field_values
                })
        
        # Field values filtering already happened during extraction
        if field_values:
            logger.info(f"Found {len(items)} items in project, filtered to {len(issue_details)} issues matching the field value criteria")

        return issue_details

    except subprocess.CalledProcessError as e:
        logger.error(f"Error accessing project {project_url}. Make sure the project exists and you have access.")
        logger.error("Add project scope like this: gh auth refresh -s project")
        if hasattr(e, 'stderr'):
            logger.error(f"stderr: {e.stderr}")
        return []
    
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing project data: {e}")
        return []
    
def get_sub_issues(
        parent_issue_url: str,
        parent_title: Optional[str] = None
        ) -> List[Dict]:
    """Get sub-issues using the GitHub Sub-issues API via gh CLI.
    
    Args:
        issue_url: The URL of the issue to fetch sub-issues for
    """
    check_gh_auth_scopes()

    # Check if the parent issue URL is provided
    if not parent_issue_url:
        logger.error("Parent issue URL must be provided to fetch sub-issues")
        raise ValueError("Parent issue URL must be provided to fetch sub-issues")

    # Use gh api to call the sub-issues endpoint with correct headers
    try:
        # Extract owner, repository, and issue number from the URL
        match = re.match(r'https://github\.com/([^/]+)/([^/]+)/issues/(\d+)', parent_issue_url)
        if not match:
            logger.error(f"Invalid issue URL format: {parent_issue_url}")
            return []
        
        owner, repository, issue_number = match.groups()
        repo = f"{owner}/{repository}"
        api_endpoint = f"/repos/{owner}/{repository}/issues/{issue_number}/sub_issues"
        
        # Use gh api command with the correct headers as specified in the GitHub API docs
        cmd = [
            "gh", "api",
            "-H", "Accept: application/vnd.github+json",
            "-H", "X-GitHub-Api-Version: 2022-11-28",
            api_endpoint
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.debug(f"Command completed with exit code: {result.returncode}")
        sub_issues_data = json.loads(result.stdout)
        log_json(sub_issues_data, f"Sub-issues data for {repo}#{issue_number}:")
        
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
                logger.info(f"  - Found: https://github.com/{sub_repo}/issues/{sub_issue_number}")
                cmd = ["gh", "issue", "view", sub_issue_number, "--repo", sub_repo, "--json", "url,title,labels,number,state,closedAt"]
                logger.debug(f"Running command: {' '.join(cmd)}")
                sub_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.debug(f"Command completed with exit code: {sub_result.returncode}")
                detailed_sub_issue = json.loads(sub_result.stdout)
                log_json(detailed_sub_issue, f"Detailed sub-issue data for {sub_repo}#{sub_issue_number}:")

                # target_date, comment_timestamp, comment_url = get_target_date_from_comments(sub_repo, sub_issue_number)
                # detailed_sub_issue["target_date"] = target_date if target_date else "N/A"
                # detailed_sub_issue["last_updated_at"] = comment_timestamp if comment_timestamp else "N/A"
                # detailed_sub_issue["comment_url"] = comment_url if comment_url else "N/A"
                
                # Add parent issue information
                detailed_sub_issue["parent_url"] = parent_issue_url
                detailed_sub_issue["parent_title"] = parent_title if parent_title else f"{repo}#{issue_number}"
                
                sub_issues.append(detailed_sub_issue)
            else:
                logger.warning(f"  - Incomplete sub-issue data: {sub_issue}")
        
        return sub_issues
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting sub-issues for {repo}#{issue_number}: {e}")
        if hasattr(e, 'stderr'):
            logger.error(f"stderr: {e.stderr}")
        return []

def check_gh_auth_scopes() -> None:
    """Check if GitHub CLI is installed and has the necessary project scope"""
    # Check if gh CLI is installed
    if not shutil.which("gh"):
        raise RuntimeError("GitHub CLI (gh) not found. Please install it: https://cli.github.com/")
    
    # Check if user has the required project scope
    try:
        # First run gh auth status and grep for scopes to get just the scope information
        result = subprocess.run(
            ["sh", "-c", "gh auth status | grep scopes"], 
            capture_output=True, 
            text=True
        )
        
        if "project" not in result.stdout.lower():
            logger.warning("GitHub CLI doesn't have project scope authorization.")
            logger.warning("Run 'gh auth refresh -s project' to add the required scope.")
            sys.exit(1)
    except subprocess.SubprocessError:
        logger.warning("Failed to check GitHub authorization scopes.")

if __name__ == "__main__":
    try:
        # Set up argument parser
        parser = argparse.ArgumentParser(description="Get GitHub issues from a project with filtering options")
        parser.add_argument("project_url", help="GitHub project URL (org, user, or repo project)")
        parser.add_argument("--field", "-f", action="append", nargs=2, metavar=("NAME", "VALUE"), 
                           help="Items where custom field _is_ specified value in format: 'field_name field_value'. Can be used multiple times.")
        parser.add_argument("--fieldIsNot", "-n", action="append", nargs=2, metavar=("NAME", "VALUE"), 
                           help="Items where custom field is _not_ specified value in format: 'field_name field_value'. Can be used multiple times.")
        parser.add_argument("--output", "-o", help="Output format: 'list' (default), 'csv' (🐈-separated values), 'markdown', or 'json'")
        parser.add_argument("--subissues", "-s", action="store_true", help="Include sub-issues in the output")
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
        parser.add_argument("--quiet", "-q", action="store_true", help="Suppress all non-essential output")
        
        args = parser.parse_args()
        
        # Configure logging based on command line options
        if args.verbose:
            logger.setLevel(logging.DEBUG)
            handler.setLevel(logging.DEBUG)
        elif args.quiet:
            logger.setLevel(logging.ERROR)
            handler.setLevel(logging.ERROR)
        else:
            logger.setLevel(logging.WARNING)
            handler.setLevel(logging.WARNING)

        # Convert field arguments to a dictionary
        field_values = {}
        if args.field:
            for field_name, field_value in args.field:
                field_values[field_name] = field_value
        
        # Convert negative field arguments to a list of tuples
        negative_field_values = []
        if args.fieldIsNot:
            for field_name, field_value in args.fieldIsNot:
                negative_field_values.append((field_name, field_value))

        # Get issues with the specified filters
        issue_details = get_issues(args.project_url, field_values, negative_field_values)
        if not issue_details:
            print("No matching issues found.")
            sys.exit(0)

        # Get subissues if requested
        subissue_details = []
        if args.subissues and issue_details:
            for i in issue_details:
                subissue_details.extend(get_sub_issues(i.get('url'), parent_title=i.get('title')))
                logger.debug(f"Sub-issues for {i['url']}: {subissue_details}")

        if args.output == "json":
            import json
            print(json.dumps(issue_details, indent=2))
        elif args.output == "markdown":
            print("\n### Issues\n")
            for i in issue_details:
                print(f"- [{i['url']}]({i['url']})")
        elif args.output == "csv":
            # Default output format is a list
            separator = "🐈"
            for issue in issue_details:
                print(issue.get("title", "No title"), 
                    issue.get("url", ""), 
                    sep=separator)
            for issue in subissue_details:
                print(issue.get('parent_title', 'No parent title'),
                    issue.get("title", "No title"), 
                    issue.get("url", ""), 
                    sep=separator)
        else:
            for issue in issue_details:
                print(issue.get("url", ""))
            for issue in subissue_details:
                print(issue.get("url", ""))
                    
        
    except KeyboardInterrupt:
        logger.error("Operation canceled by user.")
        sys.exit(1)
    except RuntimeError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)