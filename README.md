# Azure DevOps to GitHub Actions Migration Agent

This repository contains a standalone migration-planning agent for moving one Azure DevOps repository and its pipelines to GitHub Actions. It is intentionally safe for sandbox use because the current implementation focuses on planning, validation, and reporting rather than writing changes to GitHub or Azure DevOps.

## What this agent does today

The supported workflow is:

1. Plan the migration
2. Run a dry-run validation of the generated plan
3. Generate a report with recommendations and rollback notes

The current implementation does not perform remote writes to GitHub or Azure DevOps. That makes it safe to run locally and review the migration plan before any real deployment work begins.

## Why the examples folder exists

The folder [examples](examples) contains generated sample artifacts for the repository migration flow. When you run the agent against a repository, it now creates a repository-scoped subfolder named after the target repository and writes the generated input payload and migration outputs there.

For example, a migration for Terraform-demo produces a folder such as [examples/terraform-demo](examples/terraform-demo) containing the generated files. The root [examples](examples) folder is therefore a working output area rather than a hardcoded example store.

## Project structure

```text
ado2github-ai-migrator-agent/
├── README.md
├── manifest.json
├── config.yaml
├── main.py
├── prompts.py
├── tools.py
├── planners.py
├── validation_engine.py
├── reporting_engine.py
├── schemas/
│   ├── discovery.py
│   ├── migration_plan.py
│   ├── github_actions.py
│   ├── validation.py
│   └── report.py
├── templates/
│   ├── github_workflow.yml
│   ├── reusable_workflow.yml
│   └── composite_action.yml
├── examples/
│   ├── example_input.json
│   └── example_output.json
└── tests/
    └── test_agent.py
```

## Step-by-step workflow

### 1. Plan the migration

Run the CLI with the Azure DevOps and GitHub repository details you want to evaluate.

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --mode plan
```

This prints the generated migration plan and writes a generated input payload to a repository-scoped folder such as [examples/terraform-demo/example_input.json](examples/terraform-demo/example_input.json) unless you override the output path.

### 2. Dry-run execution

Use the dry-run mode to validate the plan without writing files.

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --mode dry-run
```

The result includes:

- migration plan steps
- generated assets metadata
- validation status
- recommendations and rollback notes

### 3. Report generation

Use report mode when you want a Markdown report written to disk.

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --mode report `
  --output-dir C:\temp\migration-output
```

This writes a report file at the requested output directory.

### 4. Actual migrate

Use migrate mode to materialize the generated Git repository, translated workflows, and report assets locally. 

During execution:
1. **Clean Workspace Workspace**: The agent automatically clones the Azure DevOps repository content to a secure system temporary workspace that is automatically deleted when the migration completes (preventing local directory pollution).
2. **Auto-Scanning of YAML Pipelines**: The agent recursively scans the cloned repository for Azure DevOps YAML pipeline files (e.g. `azure-pipelines.yml`) and automatically translates them into native GitHub Actions workflows.
3. **No Default Template Pollution**: Generic skeleton files like `settings.yml`, default release/deployment workflows, and default `README.md` placeholders are never generated or overwritten, ensuring your output directory contains only your real repository files and actual translated workflows.
4. **Mirror-Pushing (Optional)**: If you pass a GitHub token and the `--create-remote` flag, the agent creates the remote GitHub repository, checks out all history, tags, and branches from Azure DevOps, applies the translated workflows, and pushes all history cleanly to the target GitHub repository.

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --mode migrate `
  --output-dir C:\temp\migration-output
```

This creates a repository-scoped output folder under the selected output directory, including:

- translated workflow files under `.github/workflows/`
- `migration_report.md`
- `migration_report.json`

To enable the optional remote GitHub creation and mirror-push flow, add:

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --mode migrate `
  --output-dir C:\temp\migration-output `
  --github-token $env:GITHUB_TOKEN `
  --create-remote
```

### Running Locally with an LLM (e.g., Qwen/Qwen2.5-Coder)

By default, running locally utilizes a smart, deterministic Python YAML translator fallback. If you want to use a running instance of `Qwen/Qwen2.5-Coder-7B-Instruct` (or any other OpenAI-compatible model API) to translate the pipelines, you can specify the SLM parameters:

```powershell
ollama run qwen2.5-coder:7b
```
```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --mode migrate `
  --output-dir C:\temp\migration-output `
  --slm-api-base "http://localhost:11434" `
  --slm-api-key "ollama" `
  --slm-model "qwen2.5-coder:7b"
```

You can also run it programmatically from Python:

```python
import asyncio
import json
from main import AdoGitHubMigrationAgent

agent = AdoGitHubMigrationAgent()
context = {
    "source": {
        "organization": "contoso",
        "project": "platform",
        "repository": "api-service",
    },
    "target": {
        "organization": "contoso-engineering",
        "repository": "api-service",
    },
}

plan_result = asyncio.run(agent.plan("Plan migration", context))
print(json.dumps(plan_result["migration_plan"], indent=2))

dry_run_result = asyncio.run(agent.execute(plan_result))
print(json.dumps(dry_run_result, indent=2))
```

## Input and output files

You can supply your own discovery metadata by passing a JSON file with the CLI option:

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service `
  --discovery-file C:\temp\discovery.json
```

If you do not pass a discovery file, the agent generates a reasonable discovery payload from the repository scope you provided.

## Test suite

Verify the implementation and regression tests:

```powershell
python -m unittest discover -s tests -v
```
