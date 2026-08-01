import asyncio

from ado2github_migrator.agent import AdoGitHubMigrationAgent


def test_agent_handles_azure_devops_migration_intent():
    assert AdoGitHubMigrationAgent().can_handle("Migrate this Azure DevOps pipeline to GitHub Actions")


def test_agent_requires_repository_scope_before_planning():
    result = asyncio.run(AdoGitHubMigrationAgent().plan("migrate", {}))

    assert result["status"] == "needs_input"


def test_agent_creates_read_only_repository_plan():
    result = asyncio.run(
        AdoGitHubMigrationAgent().plan(
            "migrate", 
            {
                "source": {"organization": "ado", "project": "project", "repository": "source"},
                "target": {"organization": "github", "repository": "target"},
            },
        )
    )

    assert result["status"] == "success"
    assert result["model"] == "Qwen/Qwen2.5-Coder-7B-Instruct"
