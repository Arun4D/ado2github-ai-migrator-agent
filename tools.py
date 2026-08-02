"""Deterministic utilities and orchestrator tool definitions for the migration plugin."""

from typing import Any, Dict, List


def validate_repository_scope(context: Dict[str, Any]) -> List[str]:
    """Return required repository scope fields missing from an agent context."""
    source = context.get("source", {})
    target = context.get("target", {})
    missing = [key for key in ("organization", "project", "repository") if not source.get(key)]
    missing.extend(f"target.{key}" for key in ("organization", "repository") if not target.get(key))
    return missing


def get_tool_definitions() -> List[Dict[str, Any]]:
    """Return structured tool metadata compatible with an external orchestrator."""
    return [
        {
            "name": "discover_projects",
            "description": "Discover list of projects in Azure DevOps organization.",
            "parameters": {
                "type": "object",
                "properties": {"organization": {"type": "string"}},
                "required": ["organization"],
            },
        },
        {
            "name": "discover_repositories",
            "description": "Discover Git repositories in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_build_pipelines",
            "description": "Discover classic build pipelines in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_release_pipelines",
            "description": "Discover classic release pipelines in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_yaml_pipelines",
            "description": "Discover YAML build pipelines in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_variables",
            "description": "Discover build pipeline variables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                    "pipeline_id": {"type": "integer"},
                },
                "required": ["organization", "project", "pipeline_id"],
            },
        },
        {
            "name": "discover_variable_groups",
            "description": "Discover variable groups in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_secrets",
            "description": "Identify names and classifications of secrets in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_secure_files",
            "description": "List secure library files in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_service_connections",
            "description": "List service connections in an Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_environments",
            "description": "Discover environments, approvals, and gates in Azure DevOps project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "discover_agent_pools",
            "description": "Discover agent pools configured in the organization.",
            "parameters": {
                "type": "object",
                "properties": {"organization": {"type": "string"}},
                "required": ["organization"],
            },
        },
        {
            "name": "discover_artifacts",
            "description": "Discover artifact feeds and pipeline outputs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["organization", "project"],
            },
        },
        {
            "name": "clone_repository",
            "description": "Clone ADO Git repository to orchestrator local space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "destination_path": {"type": "string"},
                },
                "required": ["url", "destination_path"],
            },
        },
        {
            "name": "mirror_repository",
            "description": "Mirror ADO Git repository directly to GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_url": {"type": "string"},
                    "target_url": {"type": "string"},
                },
                "required": ["source_url", "target_url"],
            },
        },
        {
            "name": "create_github_repository",
            "description": "Create GitHub Enterprise target repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "repository": {"type": "string"},
                    "private": {"type": "boolean", "default": True},
                },
                "required": ["organization", "repository"],
            },
        },
        {
            "name": "push_repository",
            "description": "Push local cloned repository to remote GitHub.",
            "parameters": {
                "type": "object",
                "properties": {
                    "local_path": {"type": "string"},
                    "target_url": {"type": "string"},
                },
                "required": ["local_path", "target_url"],
            },
        },
        {
            "name": "create_workflow",
            "description": "Create workflow file in GitHub Actions folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "repository": {"type": "string"},
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["organization", "repository", "file_path", "content"],
            },
        },
        {
            "name": "create_variable",
            "description": "Create repository/environment variable in GitHub Actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "repository": {"type": "string"},
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "environment": {"type": "string"},
                },
                "required": ["organization", "repository", "name", "value"],
            },
        },
        {
            "name": "create_secret",
            "description": "Create repository/environment secret reference placeholder in GitHub Actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "repository": {"type": "string"},
                    "name": {"type": "string"},
                    "environment": {"type": "string"},
                },
                "required": ["organization", "repository", "name"],
            },
        },
        {
            "name": "create_environment",
            "description": "Create environment in GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "repository": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["organization", "repository", "name"],
            },
        },
        {
            "name": "create_runner",
            "description": "Provision runner instance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "os": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["os"],
            },
        },
        {
            "name": "register_runner",
            "description": "Register runner instance with organization or repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "organization": {"type": "string"},
                    "repository": {"type": "string"},
                    "runner_id": {"type": "string"},
                },
                "required": ["organization", "runner_id"],
            },
        },
        {
            "name": "validate_workflow",
            "description": "Validate syntax of GitHub Actions workflow file.",
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
        },
        {
            "name": "generate_report",
            "description": "Publish human-readable migration and risk report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_json": {"type": "string"},
                    "destination_path": {"type": "string"},
                },
                "required": ["report_json", "destination_path"],
            },
        },
    ]
