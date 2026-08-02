======================================================
DISCOVERY REQUIREMENTS
======================================================

The agent must analyze Azure DevOps metadata to discover resources.

Use the following orchestrator tools for discovery:
- discover_projects
- discover_repositories
- discover_build_pipelines
- discover_release_pipelines
- discover_yaml_pipelines
- discover_variables
- discover_variable_groups
- discover_secrets
- discover_secure_files
- discover_service_connections
- discover_environments
- discover_agent_pools
- discover_artifacts

Discover:
- Git history, branches, tags, LFS, and submodules read-only.
- Build, deployment, and release pipelines plus variables and agent pools.
