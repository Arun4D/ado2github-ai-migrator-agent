======================================================
GIT REPOSITORY MIGRATION
======================================================

Migrate the Git repository and its history from Azure DevOps to GitHub Enterprise.

Supported Objects:
- Repositories
- Git history and commits
- Branches
- Tags
- Git LFS
- Submodules
- Repository Policies
- Branch Policies

Migration Requirements:
- Preserve commit history, branches, and tags. When cloning the source repository, the executor must fetch all remote heads into local branches (using the refspec `+refs/heads/*:refs/heads/*` with `--update-head-ok`) and download all tags (using `git fetch --tags`).
- Push local branches and tags using mirror-push (`git push --mirror`) to ensure target repository includes all branches, tags, and complete commit history.
- Create the target GitHub repository when remote creation is requested and credentials are available.

Target Objects:
- Repositories
- Branch Protection Rules

Orchestrator Tools:
- clone_repository
- mirror_repository
- create_github_repository
- push_repository

Validation:
- Validate repository migration
- Validate commit history
- Validate branches
- Validate tags
