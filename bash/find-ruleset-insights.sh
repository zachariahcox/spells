#!/usr/bin/env bash
# fetch_insights.sh
# Fetches ruleset insights for a specific repository in GitHub.
#
# Usage:
#   ./fetch_insights.sh <owner> <repo> <commit_sha>
#
# Example:
#   GITHUB_TOKEN="your_access_token" ./fetch_insights.sh myusername myrepo mycommitsha

# Check for the correct number of parameters.
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <owner> <repo> <commit_sha>"
  exit 1
fi

OWNER="$1"
REPO="$2"
BRANCH="$3"
COMMIT_SHA=$(curl -s https://api.github.com/repos/${OWNER}/${REPO}/commits/${BRANCH} | jq -r ".sha")
API_URL="https://api.github.com/repos/${OWNER}/${REPO}/rulesets/rule-suites"

# Ensure the GitHub access token is set.
if [ -z "$GITHUB_TOKEN" ]; then
  echo "Error: GITHUB_TOKEN environment variable is not set."
  exit 1
fi

echo "Fetching ruleset insights for repository ${OWNER}/${REPO}..."

# Make the API request to fetch ruleset insights
response=$(curl -s \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "$API_URL")

# Optionally parse and pretty-print the JSON using jq.
if command -v jq &> /dev/null; then
  echo "Parsed JSON response:"
  echo "$response" | jq .
else
  # If jq is not installed, escape control characters manually.
  echo "Escaped JSON response:"
  printf '%s' "$response" | sed -E 's/\\/\\\\/g; s/"/\\"/g; s/\n/\\n/g; s/\r/\\r/g; s/\t/\\t/g'
fi

# Look for a ruleset with the matching commit SHA
matching_ruleset=$(echo "$response" | jq -r ".[] | select(.after_sha == \"$COMMIT_SHA\")")

if [ -n "$matching_ruleset" ]; then
  echo "Matching ruleset found:"
  echo "$matching_ruleset" | jq .
else
  echo "No matching ruleset found for commit SHA: $COMMIT_SHA"
fi