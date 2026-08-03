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
- Preserve commit history where supported by the source and the target Git tooling.
- Preserve branches and tags in the target GitHub repository.
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
