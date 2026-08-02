"""Standalone Azure DevOps to GitHub Actions migration-agent plugin."""

import argparse
import asyncio
import json
from typing import Any, Protocol

from tools import validate_repository_scope

try:
    from app.services.plugin_manager import IAgent
except ImportError:
    class IAgent:  # type: ignore[no-redef]
        """Fallback used when the agent runs outside slm-enterprise-ai-platform."""


DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


class OrchestratorSLMService(Protocol):
    """Minimal optional interface supplied by the enterprise platform."""

    available: bool

    def classify_intent_sync(self, intent: str, choices: list[tuple[str, str]]) -> str: ...


class AdoGitHubMigrationAgent(IAgent):
    """Creates safe, repository-scoped Azure DevOps migration plans."""

    def __init__(self) -> None:
        self.name = "ado_github_migration_agent"
        self.version = "0.1.0"
        self._slm_service: OrchestratorSLMService | None = None

    def set_slm_service(self, service: OrchestratorSLMService) -> None:
        """Receive the model service injected by the enterprise orchestrator."""
        self._slm_service = service

    def can_handle(self, intent: str) -> bool:
        if self._slm_service is not None and self._slm_service.available:
            return self._slm_service.classify_intent_sync(
                intent,
                [
                    (self.name, "Migrate Azure DevOps Git repositories and pipelines to GitHub Actions"),
                    ("other_agent", "Requests unrelated to Azure DevOps or GitHub Actions migration"),
                ],
            ) == self.name
        keywords = ("azure devops", "ado", "azure pipeline", "github actions", "release pipeline")
        return any(keyword in intent.lower() for keyword in keywords)

    async def plan(self, intent: str, context: dict[str, Any]) -> dict[str, Any]:
        missing = validate_repository_scope(context)
        if missing:
            return {"status": "needs_input", "missing": missing}
        return {
            "status": "success",
            "model": DEFAULT_MODEL,
            "source": context["source"],
            "target": context["target"],
            "steps": [
                "Discover Git history, branches, tags, LFS, and submodules read-only",
                "Discover build, deployment, and release pipelines plus variables and agent pools",
                "Map secrets by name only and map Windows/Linux agents to GitHub runners",
                "Generate GitHub Actions recommendations for human review",
                "Require approved plan before any remote write",
            ],
        }

    async def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("status") != "success":
            return {"status": "failed", "error": "Invalid migration plan"}
        return {
            "status": "dry_run",
            "message": "No Azure DevOps or GitHub changes were made.",
            "plan": plan,
        }

    async def summarize(self, result: dict[str, Any]) -> str:
        if result.get("status") == "dry_run":
            return "### Migration Plan\n\nRepository-scoped dry run completed. No remote changes were made."
        return f"### Migration Plan\n\nStatus: {result.get('status', 'unknown')}"


def standalone_main() -> None:
    parser = argparse.ArgumentParser(description="Azure DevOps to GitHub Actions migration agent")
    parser.add_argument("--ado-organization", required=True)
    parser.add_argument("--ado-project", required=True)
    parser.add_argument("--ado-repository", required=True)
    parser.add_argument("--github-organization", required=True)
    parser.add_argument("--github-repository", required=True)
    args = parser.parse_args()
    agent = AdoGitHubMigrationAgent()
    plan = asyncio.run(
        agent.plan(
            "Plan Azure DevOps to GitHub Actions migration",
            {
                "source": {"organization": args.ado_organization, "project": args.ado_project, "repository": args.ado_repository},
                "target": {"organization": args.github_organization, "repository": args.github_repository},
            },
        )
    )
    print(json.dumps(asyncio.run(agent.execute(plan)), indent=2))


if __name__ == "__main__":
    standalone_main()
