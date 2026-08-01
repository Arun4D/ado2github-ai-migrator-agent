# Azure DevOps to GitHub Actions Migration Agent

An enterprise-oriented, AI-assisted scaffold for migrating one Azure DevOps (ADO) Git repository and its corresponding build, deployment, and release pipelines to one GitHub repository and GitHub Actions implementation.

## Included scope

- Repository-scoped lifecycle guards and REST API foundation.
- Adapter boundaries for Azure DevOps, GitHub, storage, plugins, and interchangeable AI providers.
- Architecture, data model, persistence outline, and container deployment scaffold.
- Focused implementation brief: [`prompts/BUILD_AZURE_DEVOPS_TO_GITHUB_ACTIONS_AGENT.md`](prompts/BUILD_AZURE_DEVOPS_TO_GITHUB_ACTIONS_AGENT.md).
- Default SLM: `Qwen/Qwen2.5-Coder-7B-Instruct`, served through an OpenAI-compatible endpoint.
- Plugin compatibility with the `IAgent` contract used by `Arun4D/scom-infra-pulse-agent`.

## Quick start

1. Install the package with `pip install -e .`.
2. Run the API: `uvicorn ado2github_migrator.interfaces.api:app --reload`.
3. Create a dry-run migration run through `POST /v1/migration-runs`.
4. Implement and configure read-only ADO/GitHub discovery adapters before enabling an approved migration execution path.

## Guardrails

Keep credentials in environment variables or a secret store. Create and approve one migration run per repository. Project-level work items, boards, test plans, and shared assets are deliberately out of scope unless separately planned.
