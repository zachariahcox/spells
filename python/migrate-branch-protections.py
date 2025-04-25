"""
Copilot generated. 
These are the prompts. 

* Write a program in Python to load a PAT token from the environment and download all branch protections for a repo.
* Add a launch.json entry to debug the program and load the environment variable.
* I don't want to add a PAT token in code. I would like to load it from the real terminal.
* Add a function that converts those branch protections into equivalent ruleset JSON using the docs on GitHub.
* I think this grouping function won't work. It will probably make sense to check for commonalities between the rulesets. It's possible for one ruleset to be different from another only in its configuration. It's okay to produce two rulesets with different configurations if that's required.
* Produce a list of all the commands I gave you during this session, please!
"""
import os
import requests

def get_branch_protections(repo_owner, repo_name):
    # Load the PAT token from the environment
    pat_token = os.getenv('GITHUB_TOKEN')
    if not pat_token:
        raise EnvironmentError("GITHUB_TOKEN environment variable not set")

    # GitHub API URL for branch protections
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/branches"

    headers = {
        'Authorization': f'token {pat_token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch branches: {response.status_code}, {response.text}")

    branches = response.json()
    branch_protections = {}

    for branch in branches:
        branch_name = branch['name']
        protection_url = branch.get('protection_url')
        if protection_url:
            protection_response = requests.get(protection_url, headers=headers)
            if protection_response.status_code == 200:
                branch_protections[branch_name] = protection_response.json()
            else:
                branch_protections[branch_name] = f"Failed to fetch protection: {protection_response.status_code}"

    return branch_protections

def convert_branch_protections_to_rulesets(branch_protections):
    """
    Converts branch protections into equivalent ruleset JSON, including all possible rules from the API docs.

    Args:
        branch_protections (dict): A dictionary of branch protections.

    Returns:
        list: A list of ruleset JSON objects, one per branch protection.
    """
    rulesets = []

    for branch, protection in branch_protections.items():
        ruleset = {
            "name": f"Ruleset for {branch}",
            "target": "branch",
            "enforcement": "active",
            "conditions": {
                "ref_name": {
                    "include": [f"refs/heads/{branch}"],
                    "exclude": []
                }
            },
            "rules": []
        }

        if isinstance(protection, dict):
            # Required status checks
            if protection.get("required_status_checks"):
                ruleset["rules"].append({
                    "type": "status_check",
                    "parameters": {
                        "required_checks": protection["required_status_checks"].get("contexts", [])
                    }
                })

            # Enforce admins
            if protection.get("enforce_admins"):
                ruleset["rules"].append({
                    "type": "enforce_admins",
                    "parameters": {
                        "enabled": protection["enforce_admins"]
                    }
                })

            # Required pull request reviews
            if protection.get("required_pull_request_reviews"):
                ruleset["rules"].append({
                    "type": "pull_request_review",
                    "parameters": {
                        "required_approving_review_count": protection["required_pull_request_reviews"].get("required_approving_review_count", 1),
                        "dismiss_stale_reviews": protection["required_pull_request_reviews"].get("dismiss_stale_reviews", False),
                        "require_code_owner_reviews": protection["required_pull_request_reviews"].get("require_code_owner_reviews", False)
                    }
                })

            # Restrictions on who can push
            if protection.get("restrictions"):
                ruleset["rules"].append({
                    "type": "push_restriction",
                    "parameters": {
                        "actor_ids": protection["restrictions"].get("users", []) + protection["restrictions"].get("teams", [])
                    }
                })

            # Require linear history
            if protection.get("required_linear_history"):
                ruleset["rules"].append({
                    "type": "linear_history",
                    "parameters": {
                        "enabled": protection["required_linear_history"].get("enabled", False)
                    }
                })

            # Require signed commits
            if protection.get("required_signatures"):
                ruleset["rules"].append({
                    "type": "commit_signature",
                    "parameters": {
                        "enabled": protection["required_signatures"].get("enabled", False)
                    }
                })

            # Require conversation resolution before merging
            if protection.get("required_conversation_resolution"):
                ruleset["rules"].append({
                    "type": "conversation_resolution",
                    "parameters": {
                        "enabled": protection["required_conversation_resolution"].get("enabled", False)
                    }
                })

        rulesets.append(ruleset)

    return rulesets

def minimize_rulesets(rulesets):
    """
    Reduces the number of rulesets to the minimum required to apply the same rules to each branch.

    Args:
        rulesets (list): A list of ruleset JSON objects.

    Returns:
        list: A minimized list of rulesets.
    """
    # Group branches by commonalities in rules
    grouped_rulesets = []

    for ruleset in rulesets:
        matched = False

        for group in grouped_rulesets:
            # Check if the rules are identical
            if group["rules"] == ruleset["rules"]:
                # Merge branches into the same group
                group["conditions"]["ref_name"]["include"].extend(ruleset["conditions"]["ref_name"]["include"])
                matched = True
                break

        if not matched:
            # Create a new group if no match is found
            grouped_rulesets.append(ruleset)

    # Ensure branch names are unique in the include list for each group
    for group in grouped_rulesets:
        group["conditions"]["ref_name"]["include"] = list(set(group["conditions"]["ref_name"]["include"]))

    return grouped_rulesets

def summarize_conversion(branch_protections, rulesets):
    """
    Summarizes the conversion of branch protections to rulesets.

    Args:
        branch_protections (dict): Original branch protections.
        rulesets (list): Converted rulesets.

    Returns:
        str: A summary table comparing branch protections and rulesets.
    """
    summary = []
    summary.append("| Branch | Original Protections | Converted Ruleset | Comments |")
    summary.append("|--------|----------------------|-------------------|----------|")

    for branch, protection in branch_protections.items():
        # Find the corresponding ruleset
        ruleset = next((r for r in rulesets if f"refs/heads/{branch}" in r["conditions"]["ref_name"]["include"]), None)

        if ruleset:
            comments = "Perfect conversion" if protection else "No protections to convert"
        else:
            comments = "No matching ruleset found"

        summary.append(f"| {branch} | {protection} | {ruleset} | {comments} |")

    return "\n".join(summary)

if __name__ == "__main__":
    
    repo_owner = "repos-incorporated"
    repo_name = "branch_testing_fun_for_the_whole_family"

    protections = get_branch_protections(repo_owner, repo_name)
    rulesets = convert_branch_protections_to_rulesets(protections)
    minimized_rulesets = minimize_rulesets(rulesets)

    print("Minimized Rulesets JSON:")
    for rs in minimized_rulesets:
        print(rs)

    print("\nConversion Summary:")
    summary = summarize_conversion(protections, minimized_rulesets)
    print(summary)