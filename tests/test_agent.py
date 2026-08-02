import asyncio
import json
import subprocess
import sys
import unittest
from pathlib import Path

from main import AdoGitHubMigrationAgent
from prompts import PromptCache, PromptLoader, PromptManager, PROMPT_DIR
from schemas.discovery import AdoDiscoveryData, AdoRepository, AdoPipeline, AdoVariable, AdoAgentPool, AdoEnvironment
from schemas.migration_plan import MigrationPlan, RepoMapping
from planners import GitRepoPlanner, VariableSecretPlanner, RunnerPlanner, EnvironmentPlanner
from validation_engine import ValidationEngine
from reporting_engine import ReportingEngine
from schemas.github_actions import GeneratedAssets, GeneratedWorkflow


class MigrationAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = AdoGitHubMigrationAgent()

    def test_handles_migration_intent(self) -> None:
        self.assertTrue(self.agent.can_handle("Migrate Azure DevOps pipeline to GitHub Actions"))

    def test_plan_requires_repository_scope(self) -> None:
        result = asyncio.run(self.agent.plan("migrate", {}))
        self.assertEqual(result["status"], "needs_input")

    def test_plan_is_repository_scoped(self) -> None:
        result = asyncio.run(
            self.agent.plan(
                "migrate",
                {
                    "source": {"organization": "ado", "project": "project", "repository": "source"},
                    "target": {"organization": "github", "repository": "target"},
                },
            )
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["model"], "Qwen/Qwen2.5-Coder-7B-Instruct")

    def test_optional_orchestrator_service_can_classify_intent(self) -> None:
        class FakeSLMService:
            available = True

            def classify_intent_sync(self, intent: str, choices: list[tuple[str, str]]) -> str:
                return "ado_github_migration_agent"

        agent = AdoGitHubMigrationAgent()
        agent.set_slm_service(FakeSLMService())  # type: ignore[arg-type]
        self.assertTrue(agent.can_handle("unrelated wording"))

    def test_standalone_command_needs_no_orchestrator(self) -> None:
        process = subprocess.run(
            [
                sys.executable,
                "main.py",
                "--ado-organization", "ado",
                "--ado-project", "project",
                "--ado-repository", "source",
                "--github-organization", "github",
                "--github-repository", "target",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        output = json.loads(process.stdout)
        self.assertEqual(output["status"], "dry_run")

    def test_prompt_cache_and_loader(self) -> None:
        cache = PromptCache()
        self.assertIsNone(cache.get("nonexistent"))
        cache.set("key1", "val1")
        self.assertEqual(cache.get("key1"), "val1")
        cache.clear()
        self.assertIsNone(cache.get("key1"))

        loader = PromptLoader(PROMPT_DIR, cache)
        # Check system prompt exists and loads correctly
        content = loader.load_prompt("00_system_prompt.md")
        self.assertIn("ado2github-ai-migrator-agent", content)

        # Check FileNotFound exception
        with self.assertRaises(FileNotFoundError):
            loader.load_prompt("does-not-exist.md")

    def test_prompt_manager_formatting(self) -> None:
        cache = PromptCache()
        loader = PromptLoader(PROMPT_DIR, cache)
        manager = PromptManager(loader)

        # Write a temporary prompt file for testing variables formatting
        temp_dir = Path(__file__).parent / "temp_prompts"
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / "test_prompt.md"
        temp_file.write_text("Hello {name}!", encoding="utf-8")

        temp_loader = PromptLoader(temp_dir)
        temp_manager = PromptManager(temp_loader)
        formatted = temp_manager.format_prompt("test_prompt.md", {"name": "World"})
        self.assertEqual(formatted, "Hello World!")

        # Clean up temp file
        temp_file.unlink()
        temp_dir.rmdir()

    def test_planners_and_schemas(self) -> None:
        discovery = AdoDiscoveryData(
            organization="myorg",
            project="myproj",
            repositories=[
                AdoRepository(name="my-repo", id="r1", url="http://ado/repo", default_branch="main")
            ],
            pipelines=[
                AdoPipeline(
                    name="CI",
                    id=1,
                    type="yaml",
                    variables=[AdoVariable(name="EnvVar", value="ProdVal", is_secret=False)],
                )
            ],
            variables=[
                AdoVariable(name="SecretVar", value=None, is_secret=True, source="pipeline")
            ],
            agent_pools=[
                AdoAgentPool(name="Windows Pool", is_hosted=True, os_type="Windows"),
                AdoAgentPool(name="Custom Self Hosted", is_hosted=False, os_type="Linux"),
            ],
            environments=[
                AdoEnvironment(name="Staging", approvals=[{"type": "user"}], checks=[])
            ],
        )

        manager = PromptManager(PromptLoader(PROMPT_DIR))
        repo_planner = GitRepoPlanner(manager)
        var_planner = VariableSecretPlanner(manager)
        runner_planner = RunnerPlanner(manager)
        env_planner = EnvironmentPlanner(manager)

        mapping = repo_planner.plan(discovery, "target-org", "target-repo")
        self.assertEqual(mapping.source_repo, "my-repo")
        self.assertEqual(mapping.target_repo, "target-repo")

        vars_mapped, secs_mapped = var_planner.plan(discovery)
        self.assertEqual(len(vars_mapped), 0)  # EnvVar is under pipeline variable, SecretVar is secret
        self.assertEqual(len(secs_mapped), 1)
        self.assertEqual(secs_mapped[0].source_name, "SecretVar")

        runners_mapped = runner_planner.plan(discovery)
        self.assertEqual(len(runners_mapped), 2)
        self.assertEqual(runners_mapped[0].target_runner_label, "windows-latest")
        self.assertEqual(runners_mapped[1].runner_type, "self_hosted")

        envs_mapped = env_planner.plan(discovery)
        self.assertEqual(len(envs_mapped), 1)
        self.assertEqual(envs_mapped[0].target_name, "staging")
        self.assertTrue(envs_mapped[0].approvals_required)

    def test_validation_and_reporting_engines(self) -> None:
        discovery = AdoDiscoveryData(
            organization="myorg",
            project="myproj",
            repositories=[
                AdoRepository(name="my-repo", id="r1", url="http://ado/repo", default_branch="main")
            ],
            pipelines=[AdoPipeline(name="CI", id=1, type="yaml")],
        )

        plan = MigrationPlan(
            mapping=RepoMapping(
                source_org="myorg",
                source_project="myproj",
                source_repo="my-repo",
                target_org="torg",
                target_repo="trepo",
            )
        )

        # Test valid YAML workflow
        assets = GeneratedAssets(
            workflows=[
                GeneratedWorkflow(
                    name="CI",
                    file_path=".github/workflows/ci.yml",
                    content="name: CI\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo",
                    description="Standard build workflow",
                )
            ]
        )

        validator = ValidationEngine()
        report = validator.validate(discovery, plan, assets)
        self.assertEqual(report.overall_status, "passed")

        # Test invalid/empty YAML workflow
        bad_assets = GeneratedAssets(
            workflows=[
                GeneratedWorkflow(
                    name="CI",
                    file_path=".github/workflows/ci.yml",
                    content="not-yaml: [unbalanced brackets",
                    description="Standard build workflow",
                )
            ]
        )
        bad_report = validator.validate(discovery, plan, bad_assets)
        self.assertEqual(bad_report.overall_status, "failed")

        # Test report builder output
        reporter = ReportingEngine()
        rep = reporter.generate_report(discovery, plan, report, assets)
        self.assertGreater(len(rep.rollback_plan), 0)
        self.assertEqual(rep.technical_summary.total_pipelines_converted, 1)


if __name__ == "__main__":
    unittest.main()
