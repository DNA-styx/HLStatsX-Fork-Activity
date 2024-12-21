import requests
import os

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

# Function to get unique commit SHAs of a repository
def get_unique_commits(owner, repo, token):
    commits = set()
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    headers = {"Authorization": f"token {token}"}
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        for commit in response.json():
            commits.add(commit["sha"])
        url = response.links.get("next", {}).get("url")
    return commits

# Gather activity data recursively for forks and forks of forks
def gather_activity(owner, repo, token, depth=0, max_depth=1, parent_path=""):
    if depth > max_depth:
        return []

    forks = get_forks(owner, repo, token)
    fork_activity = []

    for fork in forks:
        fork_owner = fork["owner"]["login"]
        fork_repo = fork["name"]
        commits = get_unique_commits(fork_owner, fork_repo, token)

        # Exclude forks with no code changes
        if commits:
            path = f"{parent_path}/{fork_owner}/{fork_repo}"
            fork_activity.append({"fork": fork, "commits": len(commits), "path": path})
            # Recursively gather activity data for forks of forks
            fork_activity.extend(gather_activity(fork_owner, fork_repo, token, depth + 1, max_depth, path))

    return fork_activity

# Generate HTML page
def generate_html(fork_activity):
    html = """
    <html>
    <head>
        <title>Fork Activity</title>
        <style>
            ul { list-style-type: none; }
            .repo { margin-left: 20px; }
        </style>
    </head>
    <body>
        <h1>Fork Activity</h1>
        <ul>
    """
    def add_fork_to_html(activity, depth=0):
        repo_url = activity['fork']['html_url']
        repo_name = activity['fork']['full_name']
        commits = activity['commits']
        html_part = f'<li class="repo" style="margin-left:{depth * 20}px">'
        html_part += f'<a href="{repo_url}" target="_blank">{repo_name}</a>: {commits} commits</li>'
        return html_part

    # Build the tree structure
    for activity in fork_activity:
        depth = activity['path'].count('/')
        html += add_fork_to_html(activity, depth)

    html += """
        </ul>
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

    fork_activity = gather_activity(owner, repo, token, max_depth=2) # Adjust max_depth as needed
    # Remove duplicates by full_name
    unique_activity = {activity['fork']['full_name']: activity for activity in fork_activity}.values()
    generate_html(unique_activity)

if __name__ == "__main__":
    main()
