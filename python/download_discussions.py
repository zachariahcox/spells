import requests
import os

# Replace these values with your information
TOKEN = os.getenv("GITHUB_TOKEN")
ORG_NAME = "cse-elt"
REPO_NAME = "cse-elt"
search_term = "zachariahcox"

GRAPHQL_URL = "https://api.github.com/graphql"

# GraphQL query to fetch discussions
query = """
query {
  repository(owner: "{ORG_NAME}", name: "{REPO_NAME}") {
    discussions(first: 100) {
      nodes {
        id
        title
        body
        url
      }
    }
  }
}
"""

def fetch_discussions(graphql_url, token, query):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    response = requests.post(graphql_url, json={"query": query}, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

# Make the GraphQL call
query = query.replace("{ORG_NAME}", ORG_NAME).replace("{REPO_NAME}", REPO_NAME)
discussions = fetch_discussions(GRAPHQL_URL, TOKEN, query)

if discussions:
    print(discussions)
else:
    print("Failed to fetch discussions.")
