import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from main import AdoGitHubMigrationAgent, build_example_input_payload, write_example_input_file, resolve_migration_paths
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
        self.assertEqual(output["status"], "success")

    def test_example_input_payload_is_generated_from_source_and_target(self) -> None:
        payload = build_example_input_payload(
            source={"organization": "ado", "project": "project", "repository": "source"},
            target={"organization": "github", "repository": "target"},
        )
        self.assertEqual(payload["source"]["repository"], "source")
        self.assertEqual(payload["target"]["repository"], "target")
        self.assertEqual(payload["discovery_data"]["repositories"][0]["name"], "source")
        self.assertEqual(payload["discovery_data"]["pipelines"][0]["name"], "source build")

    def test_example_input_file_can_be_written_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "example_input.json"
            written_path = write_example_input_file(
                output_path,
                source={"organization": "ado", "project": "project", "repository": "source"},
                target={"organization": "github", "repository": "target"},
            )
            self.assertEqual(written_path, output_path)
            self.assertTrue(output_path.exists())
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source"]["repository"], "source")

    def test_actual_migrate_writes_local_assets_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            plan_result = asyncio.run(
                self.agent.plan(
                    "migrate",
                    {
                        "source": {"organization": "ado", "project": "project", "repository": "source"},
                        "target": {"organization": "github", "repository": "target"},
                    },
                )
            )
            migrated = asyncio.run(self.agent.execute(plan_result, mode="migrate", output_dir=output_dir))
            self.assertEqual(migrated["status"], "migrated")
            self.assertTrue((output_dir / ".github" / "workflows").exists())
            self.assertTrue((output_dir / "migration_report.md").exists())
            self.assertTrue((output_dir / "migration_report.json").exists())

    def test_remote_repository_creation_can_be_executed(self) -> None:
        class FakeRemoteExecutor:
            def __init__(self) -> None:
                self.created_repositories: list[tuple[str, str, bool]] = []
                self.pushed_directories: list[tuple[Path, str]] = []
                self.cloned_repositories: list[tuple[str, Path]] = []

            def create_repository(self, organization: str, repository: str, private: bool = True) -> dict[str, str]:
                self.created_repositories.append((organization, repository, private))
                return {"html_url": f"https://github.com/{organization}/{repository}"}

            def clone_repository(self, source_url: str, destination_path: Path) -> dict[str, str]:
                self.cloned_repositories.append((source_url, destination_path))
                destination_path.mkdir(parents=True, exist_ok=True)
                return {"status": "cloned"}

            def push_directory(self, local_path: Path, target_url: str) -> dict[str, str]:
                self.pushed_directories.append((local_path, target_url))
                return {"status": "ok"}

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            plan_result = asyncio.run(
                self.agent.plan(
                    "migrate",
                    {
                        "source": {"organization": "ado", "project": "project", "repository": "source"},
                        "target": {"organization": "github", "repository": "target"},
                    },
                )
            )
            executor = FakeRemoteExecutor()
            migrated = asyncio.run(
                self.agent.execute(
                    plan_result,
                    mode="migrate",
                    output_dir=output_dir,
                    github_token="fake-token",
                    create_remote=True,
                    remote_executor=executor,
                    source_repo_url="https://dev.azure.com/ado/project/_git/source",
                )
            )
            self.assertEqual(migrated["status"], "migrated")
            self.assertEqual(executor.created_repositories[0][0], "github")
            self.assertEqual(executor.created_repositories[0][1], "target")
            self.assertEqual(executor.pushed_directories[0][1], "https://github.com/github/target")
            self.assertEqual(executor.cloned_repositories[0][0], "https://dev.azure.com/ado/project/_git/source")

    def test_repo_name_is_used_for_default_output_paths(self) -> None:
        paths = resolve_migration_paths(
            source={"organization": "ado", "project": "project", "repository": "Terraform-demo"},
            target={"organization": "github", "repository": "Terraform-demo"},
            output_dir=None,
            example_input_output=None,
        )
        self.assertIn("terraform-demo", str(paths["input_path"]))
        self.assertIn("terraform-demo", str(paths["output_dir"]))
        self.assertTrue(str(paths["output_dir"]).endswith("migration"))

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

    def test_github_remote_executor_clone_repository(self) -> None:
        from unittest.mock import patch, MagicMock
        from main import GitHubRemoteExecutor
        
        executor = GitHubRemoteExecutor(token="fake-token")
        
        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.returncode = 0
            mock_run.return_value = mock_res
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                dest_path = Path(tmp_dir) / "repo"
                result = executor.clone_repository(
                    source_url="https://dev.azure.com/org/proj/_git/repo",
                    destination_path=dest_path
                )
                
                self.assertEqual(result["status"], "cloned")
                self.assertEqual(result["source_url"], "https://dev.azure.com/org/proj/_git/repo")
                
                self.assertEqual(mock_run.call_count, 3)
                
                first_call_args = mock_run.call_args_list[0][0][0]
                self.assertEqual(first_call_args, ["git", "clone", "https://dev.azure.com/org/proj/_git/repo", str(dest_path)])
                
                second_call_args = mock_run.call_args_list[1][0][0]
                self.assertEqual(second_call_args, ["git", "fetch", "origin", "+refs/heads/*:refs/heads/*", "--update-head-ok"])
                second_call_kwargs = mock_run.call_args_list[1][1]
                self.assertEqual(second_call_kwargs["cwd"], str(dest_path))
                
                third_call_args = mock_run.call_args_list[2][0][0]
                self.assertEqual(third_call_args, ["git", "fetch", "--tags"])
                third_call_kwargs = mock_run.call_args_list[2][1]
                self.assertEqual(third_call_kwargs["cwd"], str(dest_path))

    def test_agent_plan_populates_repository_url(self) -> None:
        context = {
            "source": {"organization": "ado", "project": "project", "repository": "source"},
            "target": {"organization": "github", "repository": "target"},
        }
        result = asyncio.run(self.agent.plan("migrate", context))
        self.assertEqual(result["status"], "success")
        repo_url = result["analysis"]["source"]["repository_url"]
        self.assertEqual(repo_url, "https://dev.azure.com/ado/project/_git/source")

    def test_pipeline_planner_fallback_by_type(self) -> None:
        from planners import PipelinePlanner
        from schemas.discovery import AdoPipeline
        
        manager = PromptManager(PromptLoader(PROMPT_DIR))
        planner = PipelinePlanner(manager)
        
        # 1. Test classic_release
        release_pipeline = AdoPipeline(name="Prod CD", id=201, type="classic_release")
        assets = planner.plan(release_pipeline)
        content = assets.workflows[0].content
        self.assertIn("name: Prod CD (Release)", content)
        self.assertIn("release:", content)
        self.assertIn("workflow_dispatch:", content)
        
        # 2. Test classic_build
        classic_build = AdoPipeline(name="Build CI", id=202, type="classic_build")
        assets = planner.plan(classic_build)
        content = assets.workflows[0].content
        self.assertIn("name: Build CI (Classic Build)", content)
        self.assertIn("push:", content)
        self.assertIn("workflow_dispatch:", content)
        
        # 3. Test yaml
        yaml_build = AdoPipeline(name="YAML CI", id=203, type="yaml")
        assets = planner.plan(yaml_build)
        content = assets.workflows[0].content
        self.assertIn("name: YAML CI (YAML Build)", content)
        self.assertIn("push:", content)
        self.assertIn("pull_request:", content)


if __name__ == "__main__":
    unittest.main()
