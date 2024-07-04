import streamlit as st
import requests
from datetime import datetime
import pandas as pd

from dotenv import load_dotenv
import os

load_dotenv()

token = os.getenv('TOKEN')

headers = {
    'Authorization': f'bearer {token}'
}

def get_repo_details_and_issues(owner, repo):
    url = "https://api.github.com/graphql"
    query_template = f"""
    {{
      repository(owner: "{owner}", name: "{repo}") {{
        stargazerCount
        forkCount
        languages(first: 10) {{
          edges {{
            size
            node {{
              name
            }}
          }}
        }}
        issues(first: 100, states: CLOSED) {{
          edges {{
            node {{
              createdAt
              closedAt
            }}
          }}
        }}
      }}
    }}
    """
    response = requests.post(url, headers=headers, json={"query": query_template})
    if response.status_code != 200:
        return None, f"Failed to fetch data: {response.status_code}"
    response_data = response.json()
    if 'errors' in response_data:
        return None, f"Errors in response: {response_data['errors']}"
    return response_data, None

def calculate_average_resolution_time(issues):
    total_resolution_time = 0
    resolved_issue_count = 0

    for issue in issues:
        created_at = datetime.strptime(issue['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
        closed_at = datetime.strptime(issue['closedAt'], '%Y-%m-%dT%H:%M:%SZ')
        resolution_time = closed_at - created_at
        total_resolution_time += resolution_time.total_seconds()
        resolved_issue_count += 1

    if resolved_issue_count == 0:
        return 0

    average_resolution_time = total_resolution_time / resolved_issue_count
    return average_resolution_time / 3600  # return in hours

st.title('GitHub Repository Details')

repo_input = st.text_input('Enter the repository (format: owner/repo):')

# Search button
if st.button('Search'):
    if repo_input:
        owner_repo = repo_input.split('/')
        if len(owner_repo) == 2:
            owner, repo = owner_repo
            repo_info, error = get_repo_details_and_issues(owner, repo)

            if error:
                st.error(error)
            elif repo_info and repo_info.get('data') and repo_info['data'].get('repository'):
                # Extract repository details
                stargazers_count = repo_info['data']['repository']['stargazerCount']
                fork_count = repo_info['data']['repository']['forkCount']
                languages = repo_info['data']['repository']['languages']['edges']

                # Extract issues and calculate average resolution time
                issues = [edge['node'] for edge in repo_info['data']['repository']['issues']['edges']]
                average_time = calculate_average_resolution_time(issues)

                # Display the details
                st.write(f"**Stars:** {stargazers_count}")
                st.write(f"**Forks:** {fork_count}")
                st.write(f"**Languages:** {', '.join([language['node']['name'] for language in languages])}")
                st.write(f"**Average issue resolution time:** {average_time:.2f} hours")
            else:
                st.error(f"Repository {owner}/{repo} not found or API response is malformed.")
        else:
            st.error("Invalid repository name format. Please use the format 'owner/repo'.")
    else:
        st.error("Please enter a repository name.")
