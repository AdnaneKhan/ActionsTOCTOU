import argparse
import requests
import time
import os
import base64
from datetime import datetime, timedelta

token = os.environ.get("GH_TOKEN")
if not token:
    print("GH_TOKEN environment variable not set.")
    exit(1)

AUTH_HEADER = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}


def get_file_sha(repo, file_path, branch):
    """
    Get the SHA of a file in a GitHub repository.

    Parameters:
    repo (str): The repository in the format 'owner/repo'.
    file_path (str): The path to the file in the repository.
    branch (str): The branch where the file is located.

    Returns:
    str: The SHA of the file, or None if the file does not exist.
    """
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    params = {
        "ref": branch
    }
    response = requests.get(url, headers=AUTH_HEADER, params=params)
    if response.status_code == 200:
        return response.json()["sha"]
    else:
        return None

def get_deployment_statuses(repo, deployment_id):
    """
    Get the statuses of a deployment in a GitHub repository.

    Parameters:
    repo (str): The repository in the format 'owner/repo'.
    deployment_id (int): The ID of the deployment.

    Returns:
    list: A list of deployment statuses.
    """
    url = f"https://api.github.com/repos/{repo}/deployments/{deployment_id}/statuses"

    response = requests.get(url, headers=AUTH_HEADER)
    return response.json()

def get_head_commit(repo, target_pr):
    """
    Get the head commit of a pull request in a GitHub repository.

    Parameters:
    repo (str): The repository in the format 'owner/repo'.
    target_pr (int): The number of the pull request.

    Returns:
    str: The SHA of the head commit.
    """
    url = f"https://api.github.com/repos/{repo}/pulls/{target_pr}"

    response = requests.get(url, headers=AUTH_HEADER)
    return response.json()["head"]["sha"]

def get_deployments(repo, head_commit):
    """
    Get the deployments associated with a commit in a GitHub repository.

    Parameters:
    repo (str): The repository in the format 'owner/repo'.
    head_commit (str): The SHA of the commit.

    Returns:
    list: A list of deployments.
    """
    url = f"https://api.github.com/repos/{repo}/deployments"

    params = {
        "sha": head_commit
    }
    response = requests.get(url, headers=AUTH_HEADER, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting deployments, code: {str(response.status_code)}")
        return []

def get_labels(repo, target_pr):
    """
    Get the labels of an issue in a GitHub repository.

    Parameters:
    repo (str): The repository in the format 'owner/repo'.
    target_pr (int): The number of the issue.

    Returns:
    list: A list of labels.
    """
    url = f"https://api.github.com/repos/{repo}/issues/{target_pr}/labels"
    response = requests.get(url, headers=AUTH_HEADER)

    labels = []
    if response.status_code == 200:
        # Parse the JSON response and extract the labels
        labels = [label["name"] for label in response.json()]
    else:
        print(f"Error getting labels, code: {str(response.status_code)}")
    return labels

def get_issue_comments(repo, target_pr):
    """
    Get the comments of an issue in a GitHub repository.

    Parameters:
    repo (str): The repository in the format 'owner/repo'.
    target_pr (int): The number of the issue.

    Returns:
    list: A list of comments.
    """
    url = f"https://api.github.com/repos/{repo}/issues/{target_pr}/comments"

    since = (datetime.utcnow() - timedelta(minutes=2)).replace(microsecond=0).isoformat()
    params = {
        "per_page": 5,
        "since": since+"Z"
    }
    response = requests.get(url, headers=AUTH_HEADER, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting issue comments, code: {str(response.status_code)}")
        return []

def create_or_update_file(fork_repo, fork_branch,file_content,file_path, file_sha):
    """
    Create or update a file in a GitHub repository.

    Parameters:
    fork_repo (str): The repository in the format 'owner/repo'.
    fork_branch (str): The branch where the file should be created or updated.
    file_content (bytes): The content of the file.
    file_path (str): The path to the file in the repository.
    file_sha (str): The SHA of the file, or None if the file does not exist.

    Returns:
    None
    """

    url = f"https://api.github.com/repos/{fork_repo}/contents/{file_path}"

    data = {
        "message": "[skip ci] update",
        "content": base64.b64encode(file_content).decode(),
        "branch": fork_branch
    }

    if file_sha:
        data["sha"] = file_sha
    response = requests.put(url, headers=AUTH_HEADER, json=data)
    if response.status_code in [201, 200]:
        print(f"{file_path} file created or updated in the fork repository.")
    else:
        print(f"Failed to create or update {file_path} file in the fork repository.")
        print("Response:", response.json())

def main(target_pr, repo, fork_repo, fork_branch, search_string, mode, update_file, update_path):
    """
    Main function to monitor GitHub issue comments and create or update a file in a repository.

    Parameters:
    target_pr (int): The number of the target pull request.
    repo (str): The repository in the format 'owner/repo'.
    fork_repo (str): The fork repository in the format 'owner/repo'.
    fork_branch (str): The branch in the fork repository.
    search_string (str): The specific issue comment prefix or full label to search for.
    mode (str): The mode of operation: 'comment', 'environment' or 'label'.
    update_file (str): The path to the local file to be updated.
    update_path (str): The path in the repository where the file should be updated.

    Returns:
    None
    """
    file_sha = get_file_sha(fork_repo, update_path, fork_branch)
    with open(update_file, "rb") as file:
        file_contents = file.read()

    if mode == 'comment':
        while True:
            issue_comments = get_issue_comments(repo, target_pr)
            if issue_comments:
                most_recent_comment = issue_comments[-1]["body"].strip() 
                if most_recent_comment.startswith(search_string):
                    print(f"Most recent comment starts with '{search_string}'. Proceeding to create {update_path} file.")
                  
                    create_or_update_file(fork_repo, fork_branch, file_contents, update_path, file_sha)
                    break
                else:
                    print(f"Most recent comment does not start with '{search_string}'. Retrying in 500ms...")
            else:
                print("No issue comments found. Retrying in 500ms...")
            time.sleep(0.5)
    elif mode == 'environment':
        head_commit = get_head_commit(repo, target_pr)
        deployments = get_deployments(repo, head_commit)
        if deployments:
            deployment_id = deployments[0]["id"]
            while True:
                deployment_statuses = get_deployment_statuses(repo, deployment_id)
                if any(status["state"] == "queued" for status in deployment_statuses):
                    print(f"Deployment status is 'queued'. Proceeding to create {update_path}.")

                    create_or_update_file(fork_repo, fork_branch, file_contents, update_path, file_sha)
                    break
                else:
                    print("Deployment status is not 'queued'. Retrying in 500ms...")
                    time.sleep(0.50)
        else:
            print("No deployments found for the head commit.")
    elif mode == 'label':
        while True:
            labels = get_labels(repo, target_pr)
        
            if search_string in labels:
                print(f"Label {search_string} found. Proceeding to create {update_path}.")
                create_or_update_file(fork_repo, fork_branch, file_contents, update_path, file_sha)
                break
            else:
                print(f"Label {search_string} not found. Retrying in 500ms...")
                time.sleep(.50)

    else:
        print("Invalid mode specified. Please use either 'comment' or 'environment'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor GitHub issue comments.")
    parser.add_argument("--target-pr", type=int, help="Target pull request number.")
    parser.add_argument("--repo", type=str, required=True,help="Repository in the format 'owner/repo'.")
    parser.add_argument("--fork-repo", type=str, required=True, help="Fork repository in the format 'owner/repo'.")
    parser.add_argument("--fork-branch", type=str, required=True, help="Branch name in the fork repository.")
    parser.add_argument("--mode", type=str, required=True, choices=["comment", "environment", "label"], help="Mode of operation: 'comment', 'environment' or 'label'.")
    parser.add_argument("--search-string", type=str, required=False, default="", help="Specific issue comment prefix or full label to search for.")
    parser.add_argument("--update-file", type=str, required=True, help="Path to the local file to be updated.")
    parser.add_argument("--update-path", type=str, required=True, help="Path in the repository where the file should be updated.")

    args = parser.parse_args()

    if args.mode in ["comment", "label"]:
        if not args.search_string:
            parser.error("Search string is required for 'comment' and 'label' modes.")


    main(args.target_pr, args.repo, args.fork_repo, args.fork_branch, args.search_string, args.mode, args.update_file, args.update_path)
