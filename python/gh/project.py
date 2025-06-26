"""
The script produces lists of GitHub issues referenced by GitHub projects.
The projects API has key limitations on query lengths.
Many operations require multiple queries and offline processing.

Usage:
    python project.py <project_url> [--field NAME VALUE] [--output FORMAT] [--verbose] [--quiet]
"""
import subprocess
import json
import re
import shutil
import sys
import argparse
import logging

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Allow all levels, control by handler level
handler = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
handler.setLevel(logging.ERROR)

def get_issues(project_url, field_values=None):
    """Search for GitHub issues using a query string and filter to only issues in the specified project.
    
    Args:
        project_url: The URL of the GitHub project to filter issues by. Project can contain issues from multiple repos.
        field_values: Optional dictionary of project field values to filter by {field_name: field_value}
        
    Returns:
        List of GitHub issue URLs belonging to the specified project
        
    Note:
        Logging is disabled by default. Use the --verbose flag when running this script
        or call enable_logging(True) when using this function programmatically.
    """
    # First check if a project URL is provided
    if not project_url:
        # When no project URL is provided, raise an error
        logger.error("Project URL must be provided to filter issues by project")
        raise ValueError("Project URL must be provided to filter issues by project")
    
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
            graphql_query = f"""
            query {{
                organization(login: "{org}") {{
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
        elif user_match:
            user = user_match.group(1)
            project_number = user_match.group(2)
            logger.debug(f"Fetching issues from user project: {user}/projects/{project_number}")
            
            # GraphQL query for user project
            graphql_query = f"""
            query {{
                user(login: "{user}") {{
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
        elif repo_match:
            owner = repo_match.group(1)
            repo = repo_match.group(2)
            project_number = repo_match.group(3)
            logger.debug(f"Fetching issues from repository project: {owner}/{repo}/projects/{project_number}")
            
            # GraphQL query for repository project
            graphql_query = f"""
            query {{
                repository(owner: "{owner}", name: "{repo}") {{
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
        else:
            logger.error(f"Unrecognized project URL format: {project_url}")
            return []
        
        # Run the GraphQL query using GitHub CLI with pagination
        all_data = {"data": {}}
        has_next_page = True
        end_cursor = None

        # Navigate the response structure based on the project type
        if org_match:
            node_name = "organization"
        elif user_match:
            node_name = "user"
        elif repo_match:
            node_name = "repository"
        else:
            node_name = "unknown"
        
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
        
        # Extract issue information from the result
        issue_urls = []
        issue_details = []

        # Get project fields structure
        project_data = data.get("data", {}).get(node_name, {}).get("projectV2", {})
        
        # Build lookup dictionary for fields by name
        fields = project_data.get("fields", {}).get("nodes", [])
        field_dict = {}
        for field in fields:
            if "name" in field:
                field_dict[field["name"]] = field
        
        # Extract issue URLs and other details
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
            
            # Skip this item if it doesn't match the required field values
            if field_values:
                match = True
                for field_name, expected_value in field_values.items():
                    if field_name not in item_field_values or item_field_values[field_name] != expected_value:
                        match = False
                        break
                
                if not match:
                    continue
                    
            if content and "url" in content and content.get("__typename") == "Issue":
                issue_urls.append(content["url"])
                
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
                    "state": content.get("state", "OPEN"),
                    "labels": labels,
                    "type": content.get("__typename", "Issue"),
                    "field_values": item_field_values
                })
        
        # Field values filtering already happened during extraction
        if field_values:
            logger.info(f"Found {len(items)} items in project, filtered to {len(issue_urls)} issues matching the field value criteria")
        
        return issue_urls
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error accessing project {project_url}. Make sure the project exists and you have access.")
        logger.error("Add project scope like this: gh auth refresh -s project")
        if hasattr(e, 'stderr'):
            logger.error(f"stderr: {e.stderr}")
        return []
    
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing project data: {e}")
        return []
    

def check_gh_auth_scopes():
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
        # Check GitHub CLI installation and authorization
        check_gh_auth_scopes()

        # Set up argument parser
        parser = argparse.ArgumentParser(description="Get GitHub issues from a project with filtering options")
        parser.add_argument("project_url", help="GitHub project URL (org, user, or repo project)")
        parser.add_argument("--field", "-f", action="append", nargs=2, metavar=("NAME", "VALUE"), 
                           help="Project field filter in format 'field_name field_value'. Can be used multiple times.")
        parser.add_argument("--output", "-o", help="Output format: 'urls' (default), 'markdown', or 'json'")
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
        parser.add_argument("--quiet", "-q", action="store_true", help="Suppress all non-essential output")
        
        args = parser.parse_args()
        
        # Configure logging based on command line options
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        elif args.quiet:
            logger.setLevel(logging.ERROR)
        else:
            logger.setLevel(logging.WARNING)

        # Convert field arguments to a dictionary
        field_values = {}
        if args.field:
            for field_name, field_value in args.field:
                field_values[field_name] = field_value
        
        # Get issues with the specified filters
        issue_urls = get_issues(args.project_url, field_values)
        
        # Output based on format
        if not issue_urls:
            print("No matching issues found.")
            sys.exit(0)
            
        if args.output == "json":
            import json
            print(json.dumps(issue_urls))
        elif args.output == "markdown":
            print("\n### Issues\n")
            for url in issue_urls:
                print(f"- [{url}]({url})")
        else:
            # Default output format is just URLs
            for url in issue_urls:
                print(url)
    
    except KeyboardInterrupt:
        logger.error("Operation canceled by user.")
        sys.exit(1)
    except RuntimeError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)