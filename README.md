# ActionsTOCTOU

This PoC script contains code to monitor for an approval event (either a comment, label, or deployment environmnet approval) and then quickly replaces a file in the PR head with on specified.

This could be a script, an action.yml file. It really depends on the target workflow.

## Issue Ops TOCTOU

This is probably the most common form of the vulnerability. The `issue_comment` trigger does
not contain the pull request head sha, so most workflows that implement issue ops along with
a check that the commenter is in fact a maintainer tend to use the API to get the PR head information or use the PR number to create a ref. Regardless of what workflows do, they end up
getting the latest commit from the PR. This leaves a short window between the time the maintainer
makes the comment to approve a run and the workflow actually checking out the PR head.

If the workflow uses secrets or runs the PR code in some kind of privileged context, then an
attacker can exploit the race condition.

## Deployment Environment Approval TOCTOU

If a workflow uses pull_request_target along with the head.ref instead of head.sha, then
an attacker can again try to win the race condition and quickly update their PR as soon as they
see that the maintainer has approved the deployment.


