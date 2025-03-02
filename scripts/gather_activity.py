import requests
import os
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

# Function to get the default branch of a repository
def get_default_branch(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    repo_data = response.json()
    return repo_data["default_branch"]

# Function to get the description (About text) of a repository
def get_repo_description(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    repo_data = response.json()
    description = repo_data.get("description", "")
    return description or ""

# Function to get the number of stars of a repository
def get_repo_stars(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    repo_data = response.json()
    return repo_data["stargazers_count"]

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

# Function to get the number of commits ahead and behind the parent repository
def get_commits_ahead_behind(parent_owner, parent_repo, fork_owner, fork_repo, token):
    parent_default_branch = get_default_branch(parent_owner, parent_repo, token)
    fork_default_branch = get_default_branch(fork_owner, fork_repo, token)
    url = f"https://api.github.com/repos/{parent_owner}/{parent_repo}/compare/{parent_default_branch}...{fork_owner}:{fork_default_branch}"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    compare_data = response.json()
    return compare_data["ahead_by"], compare_data["behind_by"]

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
            # Make the commit date offset-aware
            commit_date = commit_date.replace(tzinfo=timezone.utc)
            if not last_commit_date or commit_date > last_commit_date:
                last_commit_date = commit_date
        url = response.links.get("next", {}).get("url")
    return commits, last_commit_date

# Function to get the number of open issues and the last release number of a repository
def get_repo_info(owner, repo, token):
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"token {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    repo_data = response.json()
    open_issues_count = repo_data["open_issues_count"]
    
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        release_data = response.json()
        last_release_number = release_data["tag_name"]
    else:
        last_release_number = "-"
    
    return open_issues_count, last_release_number

# Calculate the relative time from the current date
def relative_time_from_now(date):
    now = datetime.now(timezone.utc)
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
def gather_activity(parent_owner, parent_repo, owner, repo, token, depth=0, max_depth=1, parent_path=""):
    if depth > max_depth:
        return []

    forks = get_forks(owner, repo, token)
    fork_activity = []

    for fork in forks:
        fork_owner = fork["owner"]["login"]
        fork_repo = fork["name"]
        commits, last_commit_date = get_commits_info(fork_owner, fork_repo, token)

        # Get the number of commits ahead and behind the parent
        commits_ahead, commits_behind = get_commits_ahead_behind(parent_owner, parent_repo, fork_owner, fork_repo, token)

        # Ignore forks that are only "Commits Behind" and not "Commits Ahead"
        if commits_ahead == 0:
            continue

        if commits_ahead == 0 and commits_behind == 0:
            last_commit_date_rel = "-"
            open_issues_count = "-"
            last_release_number = "-"
        else:
            last_commit_date_rel = relative_time_from_now(last_commit_date)
            open_issues_count, last_release_number = get_repo_info(fork_owner, fork_repo, token)
            if open_issues_count == 0:
                open_issues_count = "-"

        # Get the description of the fork
        fork_description = get_repo_description(fork_owner, fork_repo, token)

        # Get the stars of the fork
        fork_stars = get_repo_stars(fork_owner, fork_repo, token)

        path = f"{parent_path}/{fork_owner}/{fork_repo}"
        fork_activity.append({
            "fork": fork,
            "description": fork_description,
            "stars": fork_stars,
            "commits_ahead": commits_ahead,
            "commits_behind": commits_behind,
            "last_commit_date": last_commit_date_rel,
            "open_issues_count": open_issues_count,
            "last_release_number": last_release_number,
            "path": path
        })
        # Recursively gather activity data for forks of forks
        fork_activity.extend(gather_activity(fork_owner, fork_repo, fork_owner, fork_repo, token, depth + 1, max_depth, path))

    return fork_activity

# Generate HTML page
def generate_html(fork_activity, parent_repo, parent_commits, parent_last_commit_date, parent_open_issues, parent_last_release, parent_description):
    # Get the current date
    current_date = datetime.now(timezone.utc).strftime("%d %b %Y")

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
                vertical-align: top;
            }
            th {
                background-color: #f2f2f2;
            }
            .small-font {
                font-size: small;
                padding-left: 20px; /* Indent the description more to the right */
            }
            footer {
                margin-top: 20px;
                font-size: small;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <h1>Fork Activity</h1>
        <table>
            <tr>
                <th>Repository</th>
                <th>Commits Ahead</th>
                <th>Commits Behind</th>
                <th>Last Commit</th>
                <th>Open Issues</th>
                <th>Last Release</th>
            </tr>
    """
    def add_fork_to_html(activity, depth=0):
        repo_url = activity['fork']['html_url']
        repo_name = activity['fork']['full_name']
        description = activity['description']
        stars = activity['stars']
        commits_ahead = activity['commits_ahead']
        commits_behind = activity['commits_behind']
        last_commit_date = activity['last_commit_date']
        open_issues_count = activity['open_issues_count']
        last_release_number = activity['last_release_number']
        indent = "&nbsp;" * (depth * 4)  # Indentation for tree structure
        stars_badge = f'<img src="https://img.shields.io/badge/stars-{stars}-brightgreen" alt="Stars">' if stars > 1 else ""
        html_part = f'<tr>'
        html_part += f'<td>{indent}<a href="{repo_url}" target="_blank">{repo_name}</a> {stars_badge}</td>'
        html_part += f'<td>{commits_ahead}</td>'
        html_part += f'<td>{commits_behind}</td>'
        html_part += f'<td>{last_commit_date}</td>'
        html_part += f'<td>{open_issues_count}</td>'
        html_part += f'<td>{last_release_number}</td>'
        html_part += '</tr>'
        html_part += f'<tr><td colspan="6" class="small-font">{indent}&nbsp;&nbsp;&nbsp;&nbsp;{description}</td></tr>'
        return html_part

    # Add the parent repository at the top with description
    parent_repo_url = f"https://github.com/{parent_repo}"
    parent_last_commit_relative = relative_time_from_now(parent_last_commit_date)
    parent_stars = get_repo_stars(parent_repo.split('/')[0], parent_repo.split('/')[1], os.getenv("GITHUB_TOKEN"))
    parent_stars_badge = f'<img src="https://img.shields.io/badge/stars-{parent_stars}-brightgreen" alt="Stars">' if parent_stars > 1 else ""
    html += f"""
            <tr>
                <td><a href="{parent_repo_url}" target="_blank">{parent_repo}</a> {parent_stars_badge}</td>
                <td>-</td>
                <td>-</td>
                <td>{parent_last_commit_relative}</td>
                <td>{parent_open_issues}</td>
                <td>{parent_last_release}</td>
            </tr>
            <tr><td colspan="6" class="small-font">{parent_description}</td></tr>
    """

    # Build the tree structure
    for activity in fork_activity:
        depth = activity['path'].count('/')
        html += add_fork_to_html(activity, depth)

    html += """
        </table>
        <footer>
            Generated by <a href="https://github.com/DNA-styx/HLStatsX-Fork-Activity" target="_blank">https://github.com/DNA-styx/HLStatsX-Fork-Activity</a>, last updated {}.
        </footer>
    </body>
    </html>
    """.format(current_date)

    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w") as f:
        f.write(html)

# Main function
def main():
    owner = "NomisCZ"
    repo = "hlstatsx-community-edition"
    token = os.getenv("GITHUB_TOKEN")

    # Get parent repository description, commits, last commit date, open issues, and last release number
    parent_description = get_repo_description(owner, repo, token)
    parent_commits, parent_last_commit_date = get_commits_info(owner, repo, token)
    parent_open_issues, parent_last_release = get_repo_info(owner, repo, token)
    if parent_open_issues == 0:
        parent_open_issues = "-"
    
    fork_activity = gather_activity(owner, repo, owner, repo, token, max_depth=2) # Adjust max_depth as needed
    # Remove duplicates by full_name
    unique_activity = {activity['fork']['full_name']: activity for activity in fork_activity}.values()
    generate_html(unique_activity, f"{owner}/{repo}", len(parent_commits), parent_last_commit_date, parent_open_issues, parent_last_release, parent_description)

if __name__ == "__main__":
    main()