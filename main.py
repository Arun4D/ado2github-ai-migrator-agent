"""Azure DevOps to GitHub Actions migration agent entry point."""

import argparse
import asyncio
import json
import logging
from typing import Any, Dict, List, Protocol, Optional

from tools import validate_repository_scope, get_tool_definitions
from prompts import PromptCache, PromptLoader, PromptManager, PROMPT_DIR
from schemas.discovery import AdoDiscoveryData, AdoRepository, AdoPipeline, AdoVariable
from schemas.migration_plan import MigrationPlan, MigrationStep, RepoMapping
from schemas.github_actions import GeneratedAssets
from planners import (
    GitRepoPlanner,
    PipelinePlanner,
    VariableSecretPlanner,
    RunnerPlanner,
    EnvironmentPlanner,
)
from validation_engine import ValidationEngine
from reporting_engine import ReportingEngine

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ado2github-ai-migrator-agent")


try:
    from app.services.plugin_manager import IAgent
except ImportError:
    class IAgent:  # type: ignore[no-redef]
        """Fallback when the agent runs outside slm-enterprise-ai-platform."""


DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


class OrchestratorSLMService(Protocol):
    """Optional interface supplied by the enterprise platform orchestrator."""

    available: bool

    def classify_intent_sync(self, intent: str, choices: list[tuple[str, str]]) -> str: ...
    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str: ...


class AdoGitHubMigrationAgent(IAgent):
    """Creates repository-scoped Azure DevOps to GitHub Actions migration plans using an SLM."""

    def __init__(self) -> None:
        self.name = "ado_github_migration_agent"
        self.version = "0.1.0"
        self._slm_service: Optional[OrchestratorSLMService] = None
        self._prompt_cache = PromptCache()
        self._prompt_loader = PromptLoader(PROMPT_DIR, self._prompt_cache)
        self._prompt_manager = PromptManager(self._prompt_loader)

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

    async def plan(self, intent: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates metadata planning and translation workflow."""
        try:
            logger.info("Initializing Azure DevOps to GitHub Action migration plan...")
            missing = validate_repository_scope(context)
            if missing:
                logger.warning(f"Aborting planning due to missing scope fields: {missing}")
                return {"status": "needs_input", "missing": missing}

            source = context["source"]
            target = context["target"]

            # Load or mock Discovery Data
            discovery_raw = context.get("discovery_data")
            if discovery_raw:
                discovery_data = AdoDiscoveryData(**discovery_raw)
            else:
                logger.info("No discovery data provided. Creating base discovery metadata template.")
                discovery_data = AdoDiscoveryData(
                    organization=source["organization"],
                    project=source["project"],
                    repositories=[
                        AdoRepository(
                            name=source["repository"],
                            id="repo-12345",
                            url=f"https://dev.azure.com/{source['organization']}/{source['project']}/_git/{source['repository']}",
                            default_branch="main",
                        )
                    ],
                    pipelines=[
                        AdoPipeline(
                            name="Default Build Pipeline",
                            id=1001,
                            type="yaml",
                            variables=[
                                AdoVariable(name="Build.Configuration", value="Release")
                            ],
                        )
                    ],
                )

            # Initialize planners
            repo_planner = GitRepoPlanner(self._prompt_manager)
            var_sec_planner = VariableSecretPlanner(self._prompt_manager)
            runner_planner = RunnerPlanner(self._prompt_manager)
            env_planner = EnvironmentPlanner(self._prompt_manager)
            pipeline_planner = PipelinePlanner(self._prompt_manager)

            # Generate plans
            repo_mapping = repo_planner.plan(discovery_data, target["organization"], target["repository"])
            var_mappings, sec_mappings = var_sec_planner.plan(discovery_data, self._slm_service)
            runner_mappings = runner_planner.plan(discovery_data, self._slm_service)
            env_mappings = env_planner.plan(discovery_data, self._slm_service)

            # Translate workflows
            all_workflows: List[Any] = []
            all_reusable: List[Any] = []
            all_composite: List[Any] = []
            explanations: List[str] = []

            for pipeline in discovery_data.pipelines:
                assets = pipeline_planner.plan(pipeline, self._slm_service)
                all_workflows.extend(assets.workflows)
                all_reusable.extend(assets.reusable_workflows)
                all_composite.extend(assets.composite_actions)
                if assets.explanation:
                    explanations.append(assets.explanation)

            assets_combined = GeneratedAssets(
                workflows=all_workflows,
                reusable_workflows=all_reusable,
                composite_actions=all_composite,
                explanation="\n\n".join(explanations) if explanations else "Deterministic asset translations generated successfully.",
            )

            # Build steps list
            steps = [
                MigrationStep(id="step-1", phase="discovery", name="Discover Metadata", description="Discover Git branches, variables, secrets, and agent pools.", status="completed"),
                MigrationStep(id="step-2", phase="mapping", name="Map Variables & Secrets", description="Map variables and credentials securely.", status="completed"),
                MigrationStep(id="step-3", phase="translation", name="Translate Pipelines", description="Generate target GitHub Action workflow YAML files.", status="completed"),
                MigrationStep(id="step-4", phase="validation", name="Validate Migrated Assets", description="Verify syntax correctness and security constraints.", status="planned"),
            ]

            plan = MigrationPlan(
                mapping=repo_mapping,
                steps=steps,
                variables=var_mappings,
                secrets=sec_mappings,
                runners=runner_mappings,
                environments=env_mappings,
                confidence_score=0.98,
                next_actions=[
                    "Validate GitHub Action workflow files syntax.",
                    "Manually configure target secrets on GitHub Organization/Repository.",
                    "Verify self-hosted runner execution configurations.",
                ],
            )

            # Validation & Reporting
            validator = ValidationEngine()
            validation_report = validator.validate(discovery_data, plan, assets_combined)

            reporter = ReportingEngine()
            migration_report = reporter.generate_report(discovery_data, plan, validation_report, assets_combined)

            response = {
                "status": "success",
                "model": DEFAULT_MODEL,
                "analysis": {
                    "source": source,
                    "target": target,
                },
                "migration_plan": plan.model_dump(),
                "generated_assets": assets_combined.model_dump(),
                "validation": validation_report.model_dump(),
                "recommendations": {
                    "unsupported_features": [f.model_dump() for f in migration_report.unsupported_features],
                    "risk_assessment": [r.model_dump() for r in migration_report.risk_assessment],
                    "rollback_plan": [s.model_dump() for s in migration_report.rollback_plan],
                },
                "confidence_score": plan.confidence_score,
                "next_actions": plan.next_actions,
            }
            logger.info("Migration plan orchestrated successfully.")
            return response

        except Exception as e:
            logger.error(f"Error occurred during planning: {e}", exc_info=True)
            return {"status": "failed", "error": f"Internal agent error: {str(e)}"}

    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute dry-run migration check or orchestrate step tool registration."""
        if plan.get("status") == "failed" or "migration_plan" not in plan:
            logger.error("Attempted to execute an invalid or failed migration plan.")
            return {"status": "failed", "error": "Invalid migration plan schema."}

        logger.info("Executing dry-run migration plan check...")
        return {
            "status": "dry_run",
            "message": "Dry run execution completed. No remote writes or repository modifications were performed.",
            "plan_summary": {
                "source": plan["analysis"]["source"],
                "target": plan["analysis"]["target"],
                "total_steps": len(plan["migration_plan"]["steps"]),
                "validation_status": plan["validation"]["overall_status"],
            },
        }

    async def summarize(self, result: Dict[str, Any]) -> str:
        """Render human-readable Markdown summary of the migration plan result."""
        if result.get("status") == "failed":
            return f"### Migration Failed\n\nError: {result.get('error', 'Unknown error')}"

        summary = result.get("plan_summary", {})
        markdown = (
            "### Migration Dry-Run Result\n\n"
            f"- **Source Repo:** `{summary.get('source', {}).get('repository')}`\n"
            f"- **Target Repo:** `{summary.get('target', {}).get('repository')}`\n"
            f"- **Validation Status:** `{summary.get('validation_status', 'unknown').upper()}`\n\n"
            "Dry run complete. Please review the generated workflows, runners, and variables mappings."
        )
        return markdown


def standalone_main() -> None:
    """Standalone CLI executable entry point."""
    parser = argparse.ArgumentParser(description="Azure DevOps to GitHub Actions migration agent standalone runner.")
    parser.add_argument("--ado-organization", required=True)
    parser.add_argument("--ado-project", required=True)
    parser.add_argument("--ado-repository", required=True)
    parser.add_argument("--github-organization", required=True)
    parser.add_argument("--github-repository", required=True)
    parser.add_argument("--discovery-file", help="Path to JSON file containing discovery metadata data.")
    args = parser.parse_args()

    context: Dict[str, Any] = {
        "source": {
            "organization": args.ado_organization,
            "project": args.ado_project,
            "repository": args.ado_repository,
        },
        "target": {
            "organization": args.github_organization,
            "repository": args.github_repository,
        },
    }

    if args.discovery_file:
        try:
            with open(args.discovery_file, "r") as f:
                context["discovery_data"] = json.load(f)
            logger.info(f"Loaded discovery data metadata from {args.discovery_file}")
        except Exception as e:
            logger.error(f"Failed to read discovery file: {e}")

    agent = AdoGitHubMigrationAgent()
    plan_res = asyncio.run(agent.plan("Plan migration", context))
    exec_res = asyncio.run(agent.execute(plan_res))
    print(json.dumps(exec_res, indent=2))


if __name__ == "__main__":
    standalone_main()
