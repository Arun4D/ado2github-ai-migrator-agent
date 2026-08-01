"""Plugin adapter for the Arun4D enterprise agent orchestrator contract."""

from typing import Any

from ado2github_migrator.ai.settings import DEFAULT_QWEN_CODER_MODEL

try:
    from app.services.plugin_manager import IAgent
except ImportError:
    class IAgent:  # type: ignore[no-redef]
        """Allows standalone tests when the orchestrator is not installed."""


class AdoGitHubMigrationAgent(IAgent):
    """Plans repository-scoped Azure DevOps to GitHub Actions migrations."""

    name = "ado_github_migration_agent"
    version = "0.1.0"

    def __init__(self) -> None:
        self._slm_service: Any = None

    def set_slm_service(self, service: Any) -> None:
        """Receives the orchestrator-injected SLM service; never owns credentials."""
        self._slm_service = service

    def can_handle(self, intent: str) -> bool:
        keywords = ("azure devops", "azure pipeline", "github actions", "ado", "pipeline migration", "release migration")
        normalized = intent.lower()
        if any(keyword in normalized for keyword in keywords):
            return True
        if self._slm_service is not None and getattr(self._slm_service, "available", False):
            return self._slm_service.classify_intent_sync(
                intent,
                [
                    (self.name, "Migrate one Azure DevOps repository and pipelines to GitHub Actions"),
                    ("other_agent", "A request unrelated to Azure DevOps or GitHub Actions migration"),
                ],
            ) == self.name
        return False

    async def plan(self, intent: str, context: dict[str, Any]) -> dict[str, Any]:
        source = context.get("source", {})
        target = context.get("target", {})
        missing = [key for key in ("organization", "project", "repository") if not source.get(key)]
        missing += [f"target.{key}" for key in ("organization", "repository") if not target.get(key)]
        if missing:
            return {"status": "needs_input", "missing": missing, "query": intent}
        return {
            "status": "success",
            "agent": self.name,
            "model": DEFAULT_QWEN_CODER_MODEL,
            "scope": {"source": source, "target": target},
            "steps": [
                "Discover Git refs, history, LFS, submodules, and policies read-only",
                "Discover build, deployment, and release pipelines plus dependent variables and agent pools",
                "Classify variables and secrets without reading secret values",
                "Map Windows/Linux agents to GitHub-hosted or self-hosted runners",
                "Generate a dry-run migration plan and GitHub Actions workflow recommendations",
                "Require human approval before any remote write",
            ],
        }

    async def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execution remains intentionally read-only until connectors and approval are implemented."""
        if plan.get("status") != "success":
            return {"status": "failed", "error": "Invalid migration plan"}
        return {
            "status": "dry_run",
            "result": "No external system was changed. Connector execution requires an approved plan.",
            "plan": plan,
        }

    async def summarize(self, result: dict[str, Any]) -> str:
        if result.get("status") == "dry_run":
            return "### Azure DevOps to GitHub Actions Migration\n\nA repository-scoped dry run was prepared; no external changes were made."
        return f"### Azure DevOps to GitHub Actions Migration\n\nStatus: {result.get('status', 'unknown')}"
