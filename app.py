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
              history(first: 60) {{
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

# Function to count commits in the last 60 days
def count_commits_last_60_days(commits):
    commit_count = 0
    sixty_days_ago = datetime.now() - timedelta(days=60)

    for commit in commits:
        committed_date = datetime.strptime(commit['node']['committedDate'], '%Y-%m-%dT%H:%M:%SZ')
        if committed_date >= sixty_days_ago:
            commit_count += 1

    return commit_count

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
csv_file_path = r'topthousandrepos.csv'
df = pd.read_csv(csv_file_path)

# Initialize the session state for campaign repositories
if 'campaign_repos' not in st.session_state:
    st.session_state.campaign_repos = load_campaign()

campaign_repos = st.session_state.campaign_repos

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Repo Search", "Developer Search", "Visualizations", "Campaign", "Comparison"])

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

                    # Count commits in the last 60 days
                    commits_last_60_days = count_commits_last_60_days(latest_commit_edge)

                    # Display the details
                    st.write(f"**Stars:** {stargazers_count}")
                    st.write(f"**Forks:** {fork_count}")
                    st.write(f"**Languages:** {', '.join(languages)}")
                    st.write(f"**Average issue resolution time:** {average_time_formatted}")
                    st.write(f"**Issues solved in the last 60 days:** {issues_resolved_last_60_days}")
                    st.write(f"**Commits in the last 60 days:** {commits_last_60_days}")
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
                            "issues_solved_last_60_days": issues_resolved_last_60_days,
                            "commits_last_60_days": commits_last_60_days
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

                # Count commits in the last 60 days for each repo
                total_commits_last_60_days = 0
                for repo in dev_info:
                    repo_name = repo['name']
                    owner = repo['owner']['login']
                    repo_info, error = get_repo_details_and_issues(owner, repo_name)
                    if repo_info:
                        commits_last_60_days = count_commits_last_60_days(repo_info['data']['repository']['defaultBranchRef']['target']['history']['edges'])
                        total_commits_last_60_days += commits_last_60_days

                st.write(f"**Total commits in the last 60 days:** {total_commits_last_60_days}")

            else:
                st.error(f"Developer {dev_input} not found or API response is malformed.")
        else:
            st.error("Please enter a developer username.")

with tab3:
    st.title('Visualizations')

    # Most Popular Programming Languages
    st.header('Most Popular Programming Languages')
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

    # All Identified Programming Languages with Counts
    st.header('All Identified Programming Languages with Counts')
    all_lang_counts = languages.value_counts()

    st.write("All programming language counts:")
    st.write(all_lang_counts)

    # Average Issue Resolution Time
    st.header('Average Issue Resolution Time')
    avg_resolution_time = df[df['resolution_time_hours'].notnull()]['resolution_time_hours'].mean()
    avg_resolution_time_days = avg_resolution_time / 24  # Convert to days for clarity
    st.write(f'The average issue resolution time is {avg_resolution_time_days:.2f} days.')

    # Fastest Issue Resolution Time
    st.header('Fastest Issue Resolution Time')
    fastest_resolution_times = df[(df['resolution_time_hours'].notnull()) & (df['resolution_time_hours'] > 0)].sort_values(by='resolution_time_hours').head(10)

    fig, ax = plt.subplots()
    sns.barplot(x=fastest_resolution_times['resolution_time_hours'].round(0), y=fastest_resolution_times['repo_name'], ax=ax)
    ax.set_title('Top 10 Repositories by Fastest Issue Resolution Time')
    ax.set_xlabel('Resolution Time (hours)')
    ax.set_ylabel('Repository')
    for i in range(len(fastest_resolution_times)):
        ax.text(fastest_resolution_times['resolution_time_hours'].values[i].round(0), i, str(fastest_resolution_times['resolution_time_hours'].values[i].round(0)), color='black', ha="left")
    st.pyplot(fig)

    # Community Engagement: Stars
    st.header('Community Engagement: Stars')
    top_stars_repos = df.sort_values(by='stars_count', ascending=False).head(10)

    fig, ax = plt.subplots()
    sns.barplot(x=top_stars_repos['stars_count'], y=top_stars_repos['repo_name'], ax=ax)
    ax.set_title('Top 10 Repositories by Stars')
    ax.set_xlabel('Stars')
    ax.set_ylabel('Repository')
    for i in range(len(top_stars_repos)):
        ax.text(top_stars_repos['stars_count'].values[i], i, str(top_stars_repos['stars_count'].values[i]), color='black', ha="left")
    st.pyplot(fig)

    # Community Engagement: Forks
    st.header('Community Engagement: Forks')
    top_forks_repos = df.sort_values(by='forks_count', ascending=False).head(10)

    fig, ax = plt.subplots()
    sns.barplot(x=top_forks_repos['forks_count'], y=top_forks_repos['repo_name'], ax=ax)
    ax.set_title('Top 10 Repositories by Forks')
    ax.set_xlabel('Forks')
    ax.set_ylabel('Repository')
    for i in range(len(top_forks_repos)):
        ax.text(top_forks_repos['forks_count'].values[i], i, str(top_forks_repos['forks_count'].values[i]), color='black', ha="left")
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

with tab5:
    st.title('Comparison')

    if len(campaign_repos) >= 2:
        repo_options = [f"{repo['owner']}/{repo['repo_name']}" for repo in campaign_repos]
        repo1, repo2 = st.selectbox('Select first repository to compare', repo_options), st.selectbox('Select second repository to compare', repo_options, index=1)

        if repo1 and repo2:
            repo1_data = next(repo for repo in campaign_repos if f"{repo['owner']}/{repo['repo_name']}" == repo1)
            repo2_data = next(repo for repo in campaign_repos if f"{repo['owner']}/{repo['repo_name']}" == repo2)

            st.write(f"## Comparison between {repo1} and {repo2}")

            if st.checkbox('Show Stars Comparison'):
                st.write("### Stars")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['stars']}")
                col2.write(f"**{repo2}:** {repo2_data['stars']}")

            if st.checkbox('Show Forks Comparison'):
                st.write("### Forks")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['forks']}")
                col2.write(f"**{repo2}:** {repo2_data['forks']}")

            if st.checkbox('Show Languages Comparison'):
                st.write("### Languages")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['languages']}")
                col2.write(f"**{repo2}:** {repo2_data['languages']}")

            if st.checkbox('Show Average Issue Resolution Time Comparison'):
                st.write("### Average Issue Resolution Time")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['average_issue_resolution_time']}")
                col2.write(f"**{repo2}:** {repo2_data['average_issue_resolution_time']}")

            if st.checkbox('Show Issues Solved in the Last 60 Days Comparison'):
                st.write("### Issues Solved in the Last 60 Days")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['issues_solved_last_60_days']}")
                col2.write(f"**{repo2}:** {repo2_data['issues_solved_last_60_days']}")

            if st.checkbox('Show Commits in the Last 60 Days Comparison'):
                st.write("### Commits in the Last 60 Days")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['commits_last_60_days']}")
                col2.write(f"**{repo2}:** {repo2_data['commits_last_60_days']}")

            if st.checkbox('Show Latest Commit Date Comparison'):
                st.write("### Latest Commit Date")
                col1, col2 = st.columns(2)
                col1.write(f"**{repo1}:** {repo1_data['latest_commit_date']}")
                col2.write(f"**{repo2}:** {repo2_data['latest_commit_date']}")
    else:
        st.write("Add at least two repositories to the campaign for comparison.")