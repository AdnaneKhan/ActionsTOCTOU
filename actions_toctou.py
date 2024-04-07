import argparse
import requests
import time
import os
import base64
from datetime import datetime, timedelta

def get_issue_comments(repo, target_pr, token):
    url = f"https://api.github.com/repos/{repo}/issues/{target_pr}/comments"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    since = (datetime.utcnow() - timedelta(minutes=2)).replace(microsecond=0).isoformat()
    params = {
        "per_page": 5,
        "since": since+"Z"
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()


def create_file_in_fork(fork_repo, fork_branch, token):
    url = f"https://api.github.com/repos/{fork_repo}/contents/test.txt"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "message": "[skip ci] Create test.txt",
        "content": base64.b64encode("Test new file.".encode()).decode(),
        "branch": fork_branch
    }
    response = requests.put(url, headers=headers, json=data)
    if response.status_code == 201:
        print("test.txt file created in the fork repository.")
    else:
        print("Failed to create test.txt file in the fork repository.")
        print("Response:", response.json())

def main(target_pr, repo, fork_repo, fork_branch, search_string):
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("GH_TOKEN environment variable not set.")
        return

    while True:
        issue_comments = get_issue_comments(repo, target_pr, token)
        if issue_comments:
            most_recent_comment = issue_comments[-1]["body"].strip()
            print(most_recent_comment)
            if most_recent_comment.startswith(search_string):
                print(f"Most recent comment starts with '{search_string}'. Proceeding to create test.txt file.")
                create_file_in_fork(fork_repo, fork_branch, token)
                break
            else:
                print("Most recent comment does not start with '/bench'. Retrying in 750ms...")
        else:
            print("No issue comments found. Retrying in 350ms...")
        time.sleep(0.35)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor GitHub issue comments.")
    parser.add_argument("--target_pr", type=int, help="Target pull request number.")
    parser.add_argument("--repo", type=str, help="Repository in the format 'owner/repo'.")
    parser.add_argument("--fork_repo", type=str, required=True, help="Fork repository in the format 'owner/repo'.")
    parser.add_argument("--fork_branch", type=str, required=True, help="Branch name in the fork repository.")
    parser.add_argument("--search-string", type=str, required=True, help="Comment prefix string to look for.")

    args = parser.parse_args()

    main(args.target_pr, args.repo, args.fork_repo, args.fork_branch, args.search_string)
