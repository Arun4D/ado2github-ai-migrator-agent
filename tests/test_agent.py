import asyncio
import json
import subprocess
import sys
import unittest

from main import AdoGitHubMigrationAgent


class MigrationAgentTests(unittest.TestCase):
    def test_handles_migration_intent(self) -> None:
        self.assertTrue(AdoGitHubMigrationAgent().can_handle("Migrate Azure DevOps pipeline to GitHub Actions"))

    def test_plan_requires_repository_scope(self) -> None:
        result = asyncio.run(AdoGitHubMigrationAgent().plan("migrate", {}))
        self.assertEqual(result["status"], "needs_input")

    def test_plan_is_repository_scoped(self) -> None:
        result = asyncio.run(
            AdoGitHubMigrationAgent().plan(
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
        agent.set_slm_service(FakeSLMService())
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


if __name__ == "__main__":
    unittest.main()
