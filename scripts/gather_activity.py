import requests
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Function to get forks of a repository
def get_forks(owner, repo, token):
    forks = []
    url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    headers = {"Authorization": f"token {token}"}
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        forks.extend(response.json())
        url = response.links.get("next", {}).get("url")
    return forks

# Function to get unique commit SHAs and the date of the last commit of a repository
def get_commits_info(owner, repo, token):
    commits = set()
    last_commit_date = None
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {"Authorization": f"token {token}"}
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        commit_data = response.json()
        for commit in commit_data:
            commits.add(commit["sha"])
            commit_date = datetime.strptime(commit["commit"]["committer"]["date"], "%Y-%m-%dT%H:%M:%SZ")
            if not last_commit_date or commit_date > last_commit_date:
                last_commit_date = commit_date
        url = response.links.get("next", {}).get("url")
    return commits, last_commit_date

# Calculate the relative time from the current date
def relative_time_from_now(date):
    now = datetime.utcnow()
    diff = relativedelta(now, date)
    if diff.years > 0:
        return f"{diff.years} years ago"
    elif diff.months > 0:
        return f"{diff.months} months ago"
    elif diff.days > 0:
        return f"{diff.days} days ago"
    else:
        return "today"

# Gather activity data recursively for forks and forks of forks
def gather_activity(owner, repo, token, depth=0, max_depth=1, parent_path=""):
    if depth > max_depth:
        return []

    forks = get_forks(owner, repo, token)
    fork_activity = []

    for fork in forks:
        fork_owner = fork["owner"]["login"]
        fork_repo = fork["name"]
        commits, last_commit_date = get_commits_info(fork_owner, fork_repo, token)

        # Exclude forks with no code changes
        if commits:
            path = f"{parent_path}/{fork_owner}/{fork_repo}"
            fork_activity.append({
                "fork": fork,
                "commits": len(commits),
                "last_commit_date": last_commit_date,
                "path": path
            })
            # Recursively gather activity data for forks of forks
            fork_activity.extend(gather_activity(fork_owner, fork_repo, token, depth + 1, max_depth, path))

    return fork_activity

# Generate HTML page
def generate_html(fork_activity, parent_repo, parent_commits, parent_last_commit_date):
    html = """
    <html>
    <head>
        <title>Fork Activity</title>
        <style>
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                border: 1px solid black;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        </style>
    </head>
    <body>
        <h1>Fork Activity</h1>
        <table>
            <tr>
                <th>Repository</th>
                <th>Commits</th>
                <th>Last Commit</th>
            </tr>
    """
    def add_fork_to_html(activity, depth=0):
        repo_url = activity['fork']['html_url']
        repo_name = activity['fork']['full_name']
        commits = activity['commits']
        last_commit_date = relative_time_from_now(activity['last_commit_date'])
        html_part = f'<tr style="margin-left:{depth * 20}px">'
        html_part += f'<td><a href="{repo_url}" target="_blank">{repo_name}</a></td>'
        html_part += f'<td>{commits}</td>'
        html_part += f'<td>{last_commit_date}</td>'
        html_part += '</tr>'
        return html_part

    # Add the parent repository at the top
    parent_repo_url = f"https://github.com/{parent_repo}"
    parent_last_commit_relative = relative_time_from_now(parent_last_commit_date)
    html += f"""
            <tr>
                <td><a href="{parent_repo_url}" target="_blank">{parent_repo}</a></td>
                <td>{parent_commits}</td>
                <td>{parent_last_commit_relative}</td>
            </tr>
    """

    # Build the tree structure
    for activity in fork_activity:
        depth = activity['path'].count('/')
        html += add_fork_to_html(activity, depth)

    html += """
        </table>
    </body>
    </html>
    """

    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w") as f:
        f.write(html)

# Main function
def main():
    owner = "NomisCZ"
    repo = "hlstatsx-community-edition"
    token = os.getenv("GITHUB_TOKEN")

    # Get parent repository commits and last commit date
    parent_commits, parent_last_commit_date = get_commits_info(owner, repo, token)
    
    fork_activity = gather_activity(owner, repo, token, max_depth=2) # Adjust max_depth as needed
    # Remove duplicates by full_name
    unique_activity = {activity['fork']['full_name']: activity for activity in fork_activity}.values()
    generate_html(unique_activity, f"{owner}/{repo}", len(parent_commits), parent_last_commit_date)

if __name__ == "__main__":
    main()
