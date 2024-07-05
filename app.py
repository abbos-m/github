import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the GitHub token from the environment
token = os.getenv('TOKEN')

if not token:
    st.error("GitHub token is not set. Please check your .env file.")

# Define headers for GitHub API requests
headers = {
    'Authorization': f'bearer {token}'
}

CAMPAIGN_FILE = 'campaign_data.json'

# Function to get repository details and issues
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
        issues(last: 100, states: CLOSED) {{
          edges {{
            node {{
              createdAt
              closedAt
            }}
          }}
        }}
        defaultBranchRef {{
          target {{
            ... on Commit {{
              history(first: 1) {{
                edges {{
                  node {{
                    committedDate
                    message
                    url
                  }}
                }}
              }}
            }}
          }}
        }}
        collaborators(first: 10) {{
          edges {{
            node {{
              login
              url
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
        # Handle 'FORBIDDEN' error for collaborators
        if any(error['type'] == 'FORBIDDEN' for error in response_data['errors']):
            response_data['data']['repository']['collaborators'] = {'edges': []}
        else:
            return None, f"Errors in response: {response_data['errors']}"
    return response_data, None

# Function to get developer details
def get_developer_details(username):
    url = f"https://api.github.com/users/{username}/repos"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None, f"Failed to fetch data: {response.status_code}"
    return response.json(), None

# Function to calculate average issue resolution time
def calculate_average_resolution_time(issues):
    total_resolution_time = 0
    resolved_issue_count = 0

    for issue in issues[:10]:  # Only consider the last 10 issues
        created_at = datetime.strptime(issue['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
        closed_at = datetime.strptime(issue['closedAt'], '%Y-%m-%dT%H:%M:%SZ')
        resolution_time = closed_at - created_at
        total_resolution_time += resolution_time.total_seconds()
        resolved_issue_count += 1

    if resolved_issue_count == 0:
        return 0

    average_resolution_time = total_resolution_time / resolved_issue_count
    return average_resolution_time / 3600  # return in hours

# Function to count issues resolved in the last 60 days
def count_issues_resolved_last_60_days(issues):
    resolved_count = 0
    sixty_days_ago = datetime.now() - timedelta(days=60)

    for issue in issues:
        closed_at = datetime.strptime(issue['closedAt'], '%Y-%m-%dT%H:%M:%SZ')
        if closed_at >= sixty_days_ago:
            resolved_count += 1

    return resolved_count

# Function to save campaign data to a JSON file
def save_campaign(campaign_data):
    with open(CAMPAIGN_FILE, 'w') as f:
        json.dump(campaign_data, f)

# Function to load campaign data from a JSON file
def load_campaign():
    if os.path.exists(CAMPAIGN_FILE):
        with open(CAMPAIGN_FILE, 'r') as f:
            return json.load(f)
    return []

# Load the CSV data for visualizations
csv_file_path = r'hundred_repos_data.csv'
df = pd.read_csv(csv_file_path)

# Initialize the session state for campaign repositories
if 'campaign_repos' not in st.session_state:
    st.session_state.campaign_repos = load_campaign()

campaign_repos = st.session_state.campaign_repos

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["Repo Search", "Developer Search", "Visualizations", "Campaign"])

with tab1:
    st.title('GitHub Repository Details')
    repo_input = st.text_input('Enter the repository (format: owner/repo):')
    add_to_campaign = st.button('Add to Campaign')

    if st.button('Search Repo') or add_to_campaign:
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
                    languages = [language['node']['name'] for language in repo_info['data']['repository']['languages']['edges']]

                    # Filter out "Hack" language
                    languages = [lang for lang in languages if lang != "Hack"]

                    # Extract issues and calculate average resolution time
                    issues = [edge['node'] for edge in repo_info['data']['repository']['issues']['edges']]
                    average_time = calculate_average_resolution_time(issues)

                    # Format average time to days or hours
                    if average_time > 24:
                        average_time_formatted = f"{average_time / 24:.2f} days"
                    else:
                        average_time_formatted = f"{average_time:.2f} hours"

                    # Extract latest commit details
                    latest_commit_edge = repo_info['data']['repository']['defaultBranchRef']['target']['history']['edges']
                    latest_commit = latest_commit_edge[0]['node'] if latest_commit_edge else None

                    # Extract contributors
                    contributors_edges = repo_info['data']['repository']['collaborators']['edges']
                    contributors = [edge['node'] for edge in contributors_edges]

                    # Count issues resolved in the last 60 days
                    issues_resolved_last_60_days = count_issues_resolved_last_60_days(issues)

                    # Display the details
                    st.write(f"**Stars:** {stargazers_count}")
                    st.write(f"**Forks:** {fork_count}")
                    st.write(f"**Languages:** {', '.join(languages)}")
                    st.write(f"**Average issue resolution time:** {average_time_formatted}")
                    st.write(f"**Issues solved in the last 60 days:** {issues_resolved_last_60_days}")
                    if latest_commit:
                        committed_date = datetime.strptime(latest_commit['committedDate'], '%Y-%m-%dT%H:%M:%SZ')
                        latest_commit_str = f"[{latest_commit['message']}]({latest_commit['url']}) on {committed_date.strftime('%Y-%m-%d %H:%M:%S')}"
                        st.write(f"**Latest commit:** {latest_commit_str}")
                    else:
                        latest_commit_str = "No commits found."
                        st.write("**Latest commit:** No commits found.")
                    
                    # Display contributors
                    if contributors:
                        contributors_str = ', '.join([f"[{contributor['login']}]({contributor['url']})" for contributor in contributors])
                        st.write(f"**Contributors:** {contributors_str}")
                    else:
                        contributors_str = "No contributors found."
                        st.write("**Contributors:** No contributors found.")

                    # Add to campaign if button is clicked
                    if add_to_campaign:
                        campaign_repos.append({
                            "repo_name": repo,
                            "owner": owner,
                            "stars": stargazers_count,
                            "forks": fork_count,
                            "languages": ', '.join(languages),
                            "average_issue_resolution_time": average_time_formatted,
                            "latest_commit_date": committed_date.strftime('%Y-%m-%d') if latest_commit else None,
                            "contributors": ', '.join([contributor['login'] for contributor in contributors]),
                            "issues_solved_last_60_days": issues_resolved_last_60_days
                        })
                        save_campaign(campaign_repos)  # Save the campaign data
                        st.success(f"Repository {owner}/{repo} added to the campaign.")
                        st.experimental_rerun()  # Rerun to clear the input and refresh the campaign
                else:
                    st.error(f"Repository {owner}/{repo} not found or API response is malformed.")
            else:
                st.error("Invalid repository name format. Please use the format 'owner/repo'.")
        else:
            st.error("Please enter a repository name.")

with tab2:
    st.title('GitHub Developer Details')
    dev_input = st.text_input('Enter the developer username:')

    if st.button('Search Developer'):
        if dev_input:
            dev_info, error = get_developer_details(dev_input)

            if error:
                st.error(error)
            elif dev_info:
                user_url = f"https://github.com/{dev_input}"
                st.write(f"Developer profile: [**{dev_input}**]({user_url})")
                st.write(f"Repositories contributed to by **{dev_input}**:")
                for repo in dev_info:
                    st.write(f"- [{repo['name']}]({repo['html_url']})")
            else:
                st.error(f"Developer {dev_input} not found or API response is malformed.")
        else:
            st.error("Please enter a developer username.")

with tab3:
    st.title('Visualizations')

    # Most Popular Programming Languages
    st.subheader('Most Popular Programming Languages')
    languages = df['languages'].str.split(', ').explode().dropna()
    lang_counts = languages.value_counts().head(10)

    fig, ax = plt.subplots()
    sns.barplot(x=lang_counts.values, y=lang_counts.index, ax=ax)
    ax.set_title('Top 10 Most Popular Programming Languages')
    ax.set_xlabel('Count')
    ax.set_ylabel('Programming Language')
    for i in range(len(lang_counts)):
        ax.text(lang_counts.values[i], i, str(lang_counts.values[i]), color='black', ha="left")
    st.pyplot(fig)

    st.write("Programming language counts:")
    st.write(lang_counts)

    # Average Issue Resolution Time
    st.subheader('Average Issue Resolution Time')
    avg_resolution_time = df[df['resolution_time_hours'].notnull()]['resolution_time_hours'].mean()
    avg_resolution_time_days = avg_resolution_time / 24  # Convert to days for clarity
    st.write(f'The average issue resolution time is {avg_resolution_time_days:.2f} days.')

    # Community Engagement: Stars and Forks
    st.subheader('Community Engagement: Stars and Forks')
    top_repos = df.sort_values(by='stars_count', ascending=False).head(10)

    fig, ax = plt.subplots()
    sns.barplot(x=top_repos['stars_count'], y=top_repos['repo_name'], ax=ax)
    ax.set_title('Top 10 Repositories by Stars')
    ax.set_xlabel('Stars')
    ax.set_ylabel('Repository')
    for i in range(len(top_repos)):
        ax.text(top_repos['stars_count'].values[i], i, str(top_repos['stars_count'].values[i]), color='black', ha="left")
    st.pyplot(fig)

with tab4:
    st.title('Campaign')
    if st.button('Clear Campaign'):
        campaign_repos.clear()
        save_campaign(campaign_repos)  # Clear the campaign data file
        st.experimental_rerun()

    if campaign_repos:
        st.write(f"**Total Repositories in Campaign:** {len(campaign_repos)}")
        campaign_df = pd.DataFrame(campaign_repos)

        # Download CSV button
        st.download_button(
            label="Download Campaign Data as CSV",
            data=campaign_df.to_csv(index=False).encode('utf-8'),
            file_name='campaign_data.csv',
            mime='text/csv'
        )

        st.dataframe(campaign_df)

    else:
        st.write("No repositories in the campaign. Add repositories from the Repo Search tab.")