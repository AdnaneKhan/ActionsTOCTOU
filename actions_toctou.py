import argparse
import requests
import time
import os
import base64
from datetime import datetime, timedelta

def get_file_sha(repo, file_path, branch, token):
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "ref": branch
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()["sha"]
    else:
        return None

def get_deployment_statuses(repo, deployment_id, token):
    url = f"https://api.github.com/repos/{repo}/deployments/{deployment_id}/statuses"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    return response.json()

def get_head_commit(repo, target_pr, token):
    url = f"https://api.github.com/repos/{repo}/pulls/{target_pr}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    return response.json()["head"]["sha"]

def get_deployments(repo, head_commit, token):
    url = f"https://api.github.com/repos/{repo}/deployments"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "sha": head_commit
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

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

def create_or_update_file(fork_repo, fork_branch,file_content,file_path, token, file_sha):
    url = f"https://api.github.com/repos/{fork_repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "message": "[skip ci] update",
        "content": base64.b64encode(file_content).decode(),
        "branch": fork_branch
    }

    if file_sha:
        data["sha"] = file_sha
    response = requests.put(url, headers=headers, json=data)
    if response.status_code in [201, 200]:
        print(f"{file_path} file created or updated in the fork repository.")
    else:
        print(f"Failed to create or update {file_path} file in the fork repository.")
        print("Response:", response.json())

def main(target_pr, repo, fork_repo, fork_branch, search_string, mode, update_file, update_path):
    token = os.environ.get("GH_TOKEN")
    if not token:
        print("GH_TOKEN environment variable not set.")
        return
    file_sha = get_file_sha(fork_repo, update_path, fork_branch, token)
    if mode == 'comment':
        while True:
            issue_comments = get_issue_comments(repo, target_pr, token)
            if issue_comments:
                most_recent_comment = issue_comments[-1]["body"].strip() 
                if most_recent_comment.startswith(search_string):
                    print(f"Most recent comment starts with '{search_string}'. Proceeding to create {update_path} file.")
                    with open(update_file, "rb") as file:
                        file_contents = file.read()
                    create_or_update_file(fork_repo, fork_branch, file_contents, update_path, token, file_sha)
                    break
                else:
                    print(f"Most recent comment does not start with '{search_string}'. Retrying in 350ms...")
            else:
                print("No issue comments found. Retrying in 350ms...")
            time.sleep(0.35)
    elif mode == 'environment':
        head_commit = get_head_commit(repo, target_pr, token)
        deployments = get_deployments(repo, head_commit, token)
        if deployments:
            deployment_id = deployments[0]["id"]
            while True:
                deployment_statuses = get_deployment_statuses(repo, deployment_id, token)
                if any(status["state"] == "queued" for status in deployment_statuses):
                    print(f"Deployment status is 'queued'. Proceeding to create {update_path}.")

                    with open(update_file, "rb") as file:
                        file_contents = file.read()
                    create_or_update_file(fork_repo, fork_branch, file_contents, update_path, token, file_sha)
                    break
                else:
                    print("Deployment status is not 'queued'. Retrying in 350ms...")
                    time.sleep(0.35)
        else:
            print("No deployments found for the head commit.")
    else:
        print("Invalid mode specified. Please use either 'comment' or 'environment'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor GitHub issue comments.")
    parser.add_argument("--target-pr", type=int, help="Target pull request number.")
    parser.add_argument("--repo", type=str, required=True,help="Repository in the format 'owner/repo'.")
    parser.add_argument("--fork-repo", type=str, required=True, help="Fork repository in the format 'owner/repo'.")
    parser.add_argument("--fork-branch", type=str, required=True, help="Branch name in the fork repository.")
    parser.add_argument("--mode", type=str, required=True, choices=["comment", "environment"], help="Mode of operation: 'comment' or 'environment'.")
    parser.add_argument("--search-string", type=str, required=False, default="", help="Comment ops string to search for")
    parser.add_argument("--update-file", type=str, required=True, help="Path to the local file to be updated.")
    parser.add_argument("--update-path", type=str, required=True, help="Path in the repository where the file should be updated.")


    args = parser.parse_args()

    main(args.target_pr, args.repo, args.fork_repo, args.fork_branch, args.search_string, args.mode, args.update_file, args.update_path)
