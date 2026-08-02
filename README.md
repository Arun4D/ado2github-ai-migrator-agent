# Azure DevOps to GitHub Actions Migration Agent

An independent, repository-scoped plugin for `Arun4D/slm-enterprise-ai-platform`. It plans the migration of one Azure DevOps Git repository and its build, deployment, and release pipelines to one GitHub repository using GitHub Actions.

## Target Architecture

The agent follows this modular structure:

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

## Key Components

1. **`main.py`**: Entry point loaded by the enterprise orchestrator plugin manager. It orchestrates the migration plan, registers tools, handles errors, and compiles output.
2. **`prompts.py`**: Manages template formatting, loading, and memory-caching of the modular system instructions in `prompts/`.
3. **`tools.py`**: Declares metadata-only tool definitions for discovery, repo migration, and validation.
4. **`planners.py`**: Houses reasoning flow for components (Git history, Pipelines, Variables, Secrets, Environments, Runners) using the SLM.
5. **`validation_engine.py`**: Validates workflow syntax, variable mappings, scope boundaries, and flags potential risks.
6. **`reporting_engine.py`**: Assembles comprehensive Markdown and JSON reports (Migration, Validation, Risk, Rollback, Executive Summary).
7. **`schemas/`**: Pydantic models enforcing structural parsing of discovery context and migration plans.
8. **`templates/`**: Baseline GitHub Action workflows, reusable workflows, and composite actions templates.

## Standalone Execution

The agent runs independently without external LLM connections by returning standard mock validations or dry-run schemas, making it safe for sandbox environments:

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service
```

## Test Suite

Verify all components pass SOLID and Pydantic validation checks:

```powershell
python -m unittest discover -s tests -v
```
