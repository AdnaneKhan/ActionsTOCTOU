# ActionsTOCTOU

This PoC contains code to monitor for an approval event (either a comment, label, or deployment environment approval) and then quickly replaces a file in the PR head with a local file specified as a parameter.

This could be a script, an `action.yml` file, a `package.json` file. It really depends on the target workflow.

This PoC expands upon research presented in [GitHub's Pwn Requests Article](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/) and Nikita Stupin's [PwnHub](https://github.com/nikitastupin/pwnhub) repository.

## Vulnerability Details

This PoC supports three variations of Actions TOCTOU - these are the most common that you will see in the wild. There might be other more exotic examples, and if so, feel free to create an issue and I'll see if I can add it.

In all three cases the aim is to run un-reviewed code in a privileged workflow that should be running code that has _per-run_ approval.

This PoC focuses on Public Poisoned Pipeline Execution, but it is likely that these techniques also apply to internal CI/CD red-team scenarios (such as production deployment workflows that require 2PR).

### Issue Ops TOCTOU

This is probably the most common form of the vulnerability. The `issue_comment` trigger does not contain the pull request head sha, so most workflows that implement issue ops to run PR code tend to follow a flow like this:

* **Permission Check:** Determine if the triggering actor meets some authorization criteria.
* **Ref Calculation:** Calculates the PR ref by using a format expression with the PR number or using the GitHub API to retrieve the head sha.
* **Checkout:** Uses an action or a CLI command to check out the PR code.

Regardless of what workflows do, they end up getting the latest commit from the PR. This leaves a short window between the time the maintainer makes the comment to approve the run and the workflow actually checking out the PR head.


### Deployment Environment Approval TOCTOU

Often, maintainers will use a GitHub Actions deployment environment as a gate check for external pull requests that need access to secrets. When a deployment
environment has a [required_reviewers](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment#required-reviewers) protection rule, one of the maintainers must approve the deployment in order for the workflow to run.

The workflow's metadata will be generated at the time the approval is requested. If someone updates the PR head prior to the approval, then it will generate a new approval request and the old one will remain. Normally this is not a problem, maintainers will review the newest code and ignore the old one.

Depending on how the workflow is configured, there is an opportunity to exploit a race condition. This kind of attack is *NOT* social engineering in the traditional sense, because there no way way to differentiate a legitimate workflow pending approval for unit tests and one where an attacker is waiting until the moment of approval to quickly push a new change.

If a workflow uses `pull_request_target` along with `head.ref` (or a variation of it) instead of `head.sha`, then an attacker can try to win a race condition and quickly update their PR as soon as they see that the maintainer has approved the deployment.

Typically, it takes a few second between the maintainer approving a deployment (which changes its state visible through GitHub's API) and a runner picking up the workflow. As a result, this is a very easy race condition to win.

### Label Gating TOCTOU

Finally, another gating mechanism is when a maintainer configures a workflow to
run on `pull_request_target` along with just the `labeled` event. In this scenario the workflow will run on the `labeled` event, but it will not run
if the PR creator updates the PR head code (since the `synchronize` event is not present - if it is then there is no need to win a race condition, simply update the PR).

If the workflow checks out code from a mutable reference, then an attacker has a few seconds to update their PR head, and then the workflow will run newer code. For added stealth, an attacker can force push their malicious changes off their fork once the workflow starts:

```
git reset --soft HEAD~1
git push --force
```


## Tool Usage

**This PoC tool is intended to support authorized vulnerability research only. Only use it against repositories that you control or repositories that you have permission to test. I am not responsible for the consequences of illegal use.**


### Preparation

The tool is written in python3 and only has a dependency on `requests`.

In order to use it, you need to create a GitHub PAT with the `repo` scope, and if the file you are modifying is within the `.github/workflows` directory, then you will need the `workflow` scope as well. The user must have write access to the fork as well.

The tool expects the token to be set to the `GH_TOKEN` environment variable. The tool will check every 500ms.

GitHub's API has a rate limit of 5000/hour, a request every 500ms will probably exhaust it. You should not run into rate limit issues testing a POC using two accounts that you control. If you are using this tool as part of a red team or adversary emulation exercise, then modify as you need - the code is simple.

### Examples

I've added some example vulnerable workflows to the repository and used my own account to showcase the vulnerability. **Please DO NOT create test PRs against this repository.** 

If you want to use these workflows to test, then _mirror_ the repository by using GitHub's [repository import feature](https://github.com/new/import) and create a mirror. Then, enable Actions, create a test deployment environment and required reviewers rule, and use another account to create a PR with a dummy change (like adding a newline to the README), and use the script with modified files (the `test.sh` files or the `package.json`).

The tool's help text is self-explanatory. If you use the GitHub CLI, you can pass the token like from it:

```
 GH_TOKEN=`gh auth token` python3 actions_toctou.py -h
usage: actions_toctou.py [-h] [--target-pr TARGET_PR] --repo REPO --fork-repo FORK_REPO --fork-branch FORK_BRANCH --mode
                         {comment,environment,label} [--search-string SEARCH_STRING] --update-file UPDATE_FILE
                         --update-path UPDATE_PATH

Monitor GitHub issue comments.

options:
  -h, --help            show this help message and exit
  --target-pr TARGET_PR
                        Target pull request number.
  --repo REPO           Repository in the format 'owner/repo'.
  --fork-repo FORK_REPO
                        Fork repository in the format 'owner/repo'.
  --fork-branch FORK_BRANCH
                        Branch name in the fork repository.
  --mode {comment,environment,label}
                        Mode of operation: 'comment', 'environment' or 'label'.
  --search-string SEARCH_STRING
                        Specific issue comment prefix or full label to search for.
  --update-file UPDATE_FILE
                        Path to the local file to be updated.
  --update-path UPDATE_PATH
                        Path in the repository where the file should be updated.
```

`search-string` is required for the comment and label mode. It is not used for the environment mode.

`update-file` is a path to a local file that will be written to the PR head.

`update-path` is the path in the fork to write the file to. It will be created if it does not exist, otherwise
it will update it.


## References

* https://github.com/nikitastupin/pwnhub/blob/main/scripts/exploitation/push-on-label-or-comment.sh
* https://securitylab.github.com/research/github-actions-preventing-pwn-requests/
