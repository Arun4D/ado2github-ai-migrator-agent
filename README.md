# Azure DevOps to GitHub Actions Migration Agent

An independent, repository-scoped plugin for `Arun4D/slm-enterprise-ai-platform`. It plans migration of one Azure DevOps Git repository and its build, deployment, and release pipelines to one GitHub repository using GitHub Actions.

## Structure

```text
main.py        # Plugin class and standalone runner
manifest.json  # Orchestrator metadata
config.yaml    # Model and safety configuration
prompts.py     # SLM prompts
tools.py       # Deterministic helpers
tests/         # Standard-library tests
```

## Run independently

Python 3.11+ is sufficient for the current dry-run planner; no package installation is required.

```powershell
python main.py `
  --ado-organization contoso `
  --ado-project platform `
  --ado-repository api-service `
  --github-organization contoso-engineering `
  --github-repository api-service
```

The output is JSON. It never imports or requires `slm-enterprise-ai-platform`, calls Azure DevOps, calls GitHub, or calls an AI model; it makes no remote changes.

## Test

```powershell
python -m unittest discover -s tests -v
```

The test suite verifies repository scope, independent CLI execution, and optional SLM-service injection. It uses Python's standard library only.

## Optional SLM service

`main.py` defines a local `OrchestratorSLMService` protocol. It is not an import from the enterprise platform and is not required to run this agent independently.

- **Independent mode:** no SLM is created or called. The agent uses deterministic keyword routing and returns a dry-run plan.
- **Orchestrated mode:** the platform calls `set_slm_service()` with its own service. The agent uses only `available` and `classify_intent_sync()` for intent routing.

The model names in `config.yaml` are declarative: the orchestrator selects, hosts, and injects Qwen. This agent does not own model downloads, endpoints, API keys, or credentials.

## Load with the enterprise platform

`slm-enterprise-ai-platform` currently loads a local plugin directory. Its Git-URL loader should securely clone this repository to a managed cache, pin a commit SHA, validate `manifest.json`, then call `PluginManager.load_plugin(local_clone_path)`.

The cloned plugin folder must contain the five root files shown above. The platform instantiates `AdoGitHubMigrationAgent` from `main.py` and injects its SLM service through `set_slm_service()`.

`config.yaml` declares `Qwen/Qwen2.5-Coder-7B-Instruct` as the default model and `qwen2.5-coder:1.5b` as the low-resource option. Model hosting and credentials belong to the orchestrator, not this agent.

## Safety

- Exactly one ADO repository maps to one GitHub repository per plan.
- The agent defaults to dry run and requires an approved plan before any future remote-write adapter.
- Secrets are represented only by name and classification; values must never enter prompts, logs, or generated files.
