"""Azure DevOps to GitHub Actions migration agent entry point."""

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import Any, Dict, List, Protocol, Optional, Union

from datetime import datetime, timezone

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


def resolve_migration_paths(
    source: Dict[str, Any],
    target: Dict[str, Any],
    output_dir: Optional[Union[str, Path]] = None,
    example_input_output: Optional[Union[str, Path]] = None,
) -> Dict[str, Path]:
    """Resolve default input/output paths using the repository name for a clean per-repo layout."""
    repo_name = (target.get("repository") or source.get("repository") or "migration").lower().replace(" ", "-")
    base_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "examples" / repo_name
    base_dir.mkdir(parents=True, exist_ok=True)
    input_path = Path(example_input_output) if example_input_output else base_dir / "example_input.json"
    return {
        "base_dir": base_dir,
        "input_path": input_path,
        "output_dir": base_dir / "migration",
    }


def build_example_input_payload(
    source: Dict[str, Any],
    target: Dict[str, Any],
    discovery_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a runnable example input payload from the provided source and target metadata."""
    source_org = source.get("organization") or "example-ado"
    source_project = source.get("project") or "example-project"
    source_repo = source.get("repository") or "example-repo"
    target_org = target.get("organization") or "example-github"
    target_repo = target.get("repository") or "example-target-repo"
    default_branch = source.get("default_branch") or "main"

    generated_discovery = {
        "organization": source_org,
        "project": source_project,
        "repositories": [
            {
                "name": source_repo,
                "id": f"repo-{source_repo.lower().replace('-', '_')}",
                "url": f"https://dev.azure.com/{source_org}/{source_project}/_git/{source_repo}",
                "default_branch": default_branch,
                "branches": [default_branch, "develop"],
                "tags": [],
                "has_lfs": False,
                "submodules": [],
            }
        ],
        "pipelines": [
            {
                "name": f"{source_repo} build",
                "id": 1001,
                "type": "yaml",
                "variables": [
                    {"name": "Build.Configuration", "value": "Release", "is_secret": False, "source": "pipeline"}
                ],
                "stages": [],
                "triggers": [{"branch": default_branch}],
                "schedules": [],
            }
        ],
        "variables": [
            {"name": "Build.Configuration", "value": "Release", "is_secret": False, "source": "pipeline"}
        ],
        "secrets_metadata": [],
        "agent_pools": [
            {"name": "Default Ubuntu", "is_hosted": True, "agent_count": 1, "os_type": "Linux"}
        ],
        "environments": [
            {"name": "production", "approvals": [{"type": "environment"}], "checks": []}
        ],
        "service_connections": [],
    }

    return {
        "source": {
            "organization": source_org,
            "project": source_project,
            "repository": source_repo,
        },
        "target": {
            "organization": target_org,
            "repository": target_repo,
        },
        "discovery_data": discovery_data or generated_discovery,
    }


def write_example_input_file(
    output_path: Union[str, Path],
    source: Dict[str, Any],
    target: Dict[str, Any],
    discovery_data: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write the generated example input JSON to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_example_input_payload(source, target, discovery_data=discovery_data)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


class OrchestratorSLMService(Protocol):
    """Optional interface supplied by the enterprise platform orchestrator."""

    available: bool

    def classify_intent_sync(self, intent: str, choices: list[tuple[str, str]]) -> str: ...
    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str: ...


class LocalSLMService:
    """Local OpenAI-compatible SLM service client for running outside the enterprise platform."""
    
    def __init__(self, api_base: str, model: str, api_key: str) -> None:
        self.available = True
        self.api_base = api_base
        self.model = model
        self.api_key = api_key

    def classify_intent_sync(self, intent: str, choices: list[tuple[str, str]]) -> str:
        return "ado_github_migration_agent"

    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        import urllib.request
        import urllib.error
        
        base = self.api_base.rstrip('/')
        
        endpoints = []
        if "/v1" in base:
            endpoints.append({
                "url": f"{base}/chat/completions",
                "payload": {
                    "model": self.model,
                    "messages": [{"role": "system", "content": system_prompt}] + [{"role": "user", "content": prompt}] if system_prompt else [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                },
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                "response_extractor": lambda d: d["choices"][0]["message"]["content"]
            })
        else:
            endpoints.append({
                "url": f"{base}/v1/chat/completions",
                "payload": {
                    "model": self.model,
                    "messages": [{"role": "system", "content": system_prompt}] + [{"role": "user", "content": prompt}] if system_prompt else [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                },
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                "response_extractor": lambda d: d["choices"][0]["message"]["content"]
            })
            endpoints.append({
                "url": f"{base}/api/chat",
                "payload": {
                    "model": self.model,
                    "messages": [{"role": "system", "content": system_prompt}] + [{"role": "user", "content": prompt}] if system_prompt else [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                "headers": {
                    "Content-Type": "application/json"
                },
                "response_extractor": lambda d: d["message"]["content"]
            })
            
        last_error = None
        for endpoint in endpoints:
            req = urllib.request.Request(
                endpoint["url"],
                data=json.dumps(endpoint["payload"]).encode("utf-8"),
                headers=endpoint["headers"],
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    return endpoint["response_extractor"](res_data)
            except Exception as e:
                last_error = e
                continue
                
        logger.warning(f"Local SLM generate failed: {last_error}")
        raise RuntimeError(f"Local SLM generation failed: {last_error}")


class GitHubRemoteExecutor:
    """Create a remote GitHub repository and push generated content to it using the GitHub CLI."""

    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token

    def create_repository(self, organization: str, repository: str, private: bool = True) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("A GitHub token is required for remote repository creation.")

        visibility = "--private" if private else "--public"
        env = os.environ.copy()
        env["GH_TOKEN"] = self.token
        # Create the repository server-side only. Do not ask `gh` to add a remote from this process
        # because `gh` will try to add the remote in the current working directory which may be different
        # from the generated output directory. The agent will add the authenticated remote later.
        command = ["gh", "repo", "create", f"{organization}/{repository}", visibility]
        result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "GitHub CLI repository creation failed."
            if "Resource not accessible by personal access token" in error or "createRepository" in error:
                error = (
                    "GitHub repository creation failed because the supplied token does not have repository creation permissions. "
                    "Use a token with repo:create scope or create the repository manually first."
                )
            raise RuntimeError(error)

        return {
            "html_url": f"https://github.com/{organization}/{repository}",
            "full_name": f"{organization}/{repository}",
            "private": private,
        }

    def clone_repository(self, source_url: str, destination_path: Path) -> Dict[str, Any]:
        if not source_url:
            raise RuntimeError("A source repository URL is required to clone Azure DevOps content.")
        if destination_path.exists() and any(destination_path.iterdir()):
            shutil.rmtree(destination_path)
        destination_path.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(["git", "clone", source_url, str(destination_path)], capture_output=True, text=True, env=env, check=False)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "Git clone failed."
            raise RuntimeError(error)

        # Fetch all branches from remote as local branches to ensure they are migrated
        fetch_branches = subprocess.run(
            ["git", "fetch", "origin", "+refs/heads/*:refs/heads/*", "--update-head-ok"],
            cwd=str(destination_path),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if fetch_branches.returncode != 0:
            logger.warning(
                f"Failed to fetch all remote branches as local branches: {fetch_branches.stderr.strip() or fetch_branches.stdout.strip()}"
            )

        # Fetch all tags explicitly
        fetch_tags = subprocess.run(
            ["git", "fetch", "--tags"],
            cwd=str(destination_path),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if fetch_tags.returncode != 0:
            logger.warning(
                f"Failed to fetch tags explicitly: {fetch_tags.stderr.strip() or fetch_tags.stdout.strip()}"
            )

        return {"status": "cloned", "source_url": source_url, "destination": str(destination_path)}

    def push_directory(self, local_path: Path, target_url: str) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("A GitHub token is required to push migration artifacts to GitHub.")
        if not local_path.exists():
            raise FileNotFoundError(f"Local migration directory does not exist: {local_path}")

        git_path = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
        if git_path.returncode != 0:
            raise RuntimeError("git is required to push generated artifacts to GitHub.")

        env = os.environ.copy()
        env["GH_TOKEN"] = self.token
        env["GIT_TERMINAL_PROMPT"] = "0"

        # Ensure the target URL is a git push URL. Prefer the .git form for git operations.
        push_url = target_url.rstrip("/")
        if push_url.startswith("https://") and not push_url.endswith(".git"):
            push_url = push_url + ".git"

        # When pushing over HTTPS, embed the token in the URL so git can authenticate non-interactively.
        # This is a transient URL used only for the push command in this process.
        push_url_for_git = push_url
        if push_url_for_git.startswith("https://") and self.token:
            # Insert token after the scheme: https://<token>@github.com/owner/repo.git
            push_url_for_git = push_url_for_git.replace("https://", f"https://{self.token}@", 1)
        is_git_repo = (local_path / ".git").exists()
        if not is_git_repo:
            commands = [
                (["git", "init", "-b", "main"], "initialize git repository"),
                (["git", "config", "user.name", "ado2github-ai-migrator-agent"], "configure git user name"),
                (["git", "config", "user.email", "agent@example.com"], "configure git user email"),
                (["git", "remote", "add", "origin", push_url_for_git], "add origin remote"),
                (["git", "add", "."], "stage migration artifacts"),
                (["git", "commit", "-m", "Initial migration from Azure DevOps"], "create initial commit"),
                (["git", "push", "-u", "origin", "main"], "push to GitHub"),
            ]
            for command, purpose in commands:
                result = subprocess.run(command, cwd=local_path, capture_output=True, text=True, env=env, check=False)
                if result.returncode != 0:
                    if command[:2] == ["git", "commit"] and "nothing to commit" in result.stderr.lower():
                        continue
                    if command[:4] == ["git", "remote", "add", "origin"] and "already exists" in result.stderr.lower():
                        continue
                    raise RuntimeError(f"Failed to {purpose}: {result.stderr.strip() or result.stdout.strip()}")
            return {"status": "pushed", "target_url": target_url, "mode": "initial"}

        subprocess.run(["git", "config", "user.name", "ado2github-ai-migrator-agent"], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        subprocess.run(["git", "config", "user.email", "agent@example.com"], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        subprocess.run(["git", "remote", "remove", "origin"], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        subprocess.run(["git", "remote", "add", "origin", push_url_for_git], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        subprocess.run(["git", "add", "."], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        commit_result = subprocess.run(["git", "commit", "-m", "Apply migration workflow assets"], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stderr.lower():
            raise RuntimeError(f"Failed to create migration commit: {commit_result.stderr.strip() or commit_result.stdout.strip()}")
        push_result = subprocess.run(["git", "push", "--mirror", "origin"], cwd=local_path, capture_output=True, text=True, env=env, check=False)
        if push_result.returncode != 0:
            raise RuntimeError(f"Failed to mirror repository to GitHub: {push_result.stderr.strip() or push_result.stdout.strip()}")

        return {"status": "pushed", "target_url": target_url, "mode": "mirror"}


def is_ado_pipeline_file(content: str) -> bool:
    """Detect if a file contains Azure DevOps pipeline syntax/tasks."""
    content_lower = content.lower()
    if "- task:" in content_lower:
        return True
    if "pool:" in content_lower and ("steps:" in content_lower or "stages:" in content_lower):
        return True
    return False


def map_ado_step_to_gha(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map a single Azure DevOps pipeline step/task to GitHub Actions steps."""
    gha_steps = []
    
    # 1. Check for checkout
    if "checkout" in step:
        val = step["checkout"]
        if val == "self":
            gha_steps.append({
                "name": "Checkout Code",
                "uses": "actions/checkout@v4"
            })
        return gha_steps

    display_name = step.get("displayName")
    name_field = {"name": display_name} if display_name else {}

    # 2. Check for simple scripts
    if "script" in step:
        gha_steps.append({
            **name_field,
            "run": step["script"]
        })
        return gha_steps
    if "bash" in step:
        gha_steps.append({
            **name_field,
            "run": step["bash"],
            "shell": "bash"
        })
        return gha_steps
    if "powershell" in step:
        gha_steps.append({
            **name_field,
            "run": step["powershell"],
            "shell": "powershell"
        })
        return gha_steps
    if "pwsh" in step:
        gha_steps.append({
            **name_field,
            "run": step["pwsh"],
            "shell": "pwsh"
        })
        return gha_steps

    # 3. Check for task
    task = step.get("task")
    if task:
        inputs = step.get("inputs", {})
        task_clean = task.split("@")[0].lower()
        
        if task_clean == "azurecli":
            subscription = inputs.get("azureSubscription")
            inline_script = inputs.get("inlineScript")
            script_path = inputs.get("scriptPath")
            script_type = inputs.get("scriptType")
            
            # Add azure login step
            gha_steps.append({
                "name": f"Azure Login ({subscription})" if subscription else "Azure Login",
                "uses": "azure/login@v2",
                "with": {
                    "creds": f"${{{{ secrets.AZURE_CREDENTIALS_{subscription.upper().replace('-', '_')} }}}}" if subscription else "${{ secrets.AZURE_CREDENTIALS }}"
                }
            })
            
            # Add CLI execution step
            cli_step = {
                "name": display_name or "Run Azure CLI",
                "uses": "azure/CLI@v2",
                "with": {
                    "azcliversion": "latest"
                }
            }
            if inline_script:
                cli_step["with"]["inlineScript"] = inline_script
            elif script_path:
                cli_step["with"]["inlineScript"] = f"bash {script_path}"
            
            gha_steps.append(cli_step)
            
        elif task_clean in ("publishbuildartifacts", "publishpipelineartifact"):
            path = inputs.get("PathtoPublish") or inputs.get("targetPath") or inputs.get("path") or "$(Build.ArtifactStagingDirectory)"
            path = path.replace("$(Build.ArtifactStagingDirectory)", ".")
            name = inputs.get("ArtifactName") or inputs.get("artifact") or "drop"
            gha_steps.append({
                "name": display_name or "Publish Artifact",
                "uses": "actions/upload-artifact@v4",
                "with": {
                    "name": name,
                    "path": path
                }
            })
            
        elif task_clean in ("downloadbuildartifacts", "downloadpipelineartifact"):
            name = inputs.get("artifactName") or inputs.get("artifact") or "drop"
            path = inputs.get("downloadPath") or inputs.get("path") or "$(System.ArtifactsDirectory)"
            path = path.replace("$(System.ArtifactsDirectory)", ".")
            gha_steps.append({
                "name": display_name or "Download Artifact",
                "uses": "actions/download-artifact@v4",
                "with": {
                    "name": name,
                    "path": path
                }
            })
            
        elif task_clean == "copyfiles":
            contents = inputs.get("Contents", "**")
            target_folder = inputs.get("TargetFolder", ".")
            target_folder = target_folder.replace("$(Build.ArtifactStagingDirectory)", ".")
            gha_steps.append({
                "name": display_name or "Copy Files",
                "run": f"# Copy files from ADO CopyFiles@2\n# Contents: {contents}\n# Target Folder: {target_folder}\nmkdir -p {target_folder}\ncp -r . {target_folder}"
            })
            
        else:
            input_comments = "\n".join(f"#   {k}: {v}" for k, v in inputs.items())
            gha_steps.append({
                "name": display_name or f"Task: {task}",
                "run": f"# Unmapped ADO Task: {task}\n# Inputs:\n{input_comments}\necho 'Step {task} execution placeholder'"
            })
            
    return gha_steps


def parse_and_translate_ado_yaml(content: str, rel_path: str) -> str:
    """Parse Azure DevOps YAML and map triggers, pool, stages, jobs, and tasks to GitHub Actions."""
    try:
        data = yaml.safe_load(content)
    except Exception as e:
        return f"# Failed to parse Azure DevOps YAML: {e}\n# Content:\n" + "\n".join(f"# {line}" for line in content.splitlines())

    if not isinstance(data, dict):
        return f"# Invalid Azure DevOps YAML structure.\n# Content:\n" + "\n".join(f"# {line}" for line in content.splitlines())

    # Trigger mapping
    trigger = data.get("trigger")
    on_trigger = {}
    if trigger is None:
        on_trigger = {"workflow_dispatch": {}}
    elif isinstance(trigger, list):
        on_trigger = {"push": {"branches": trigger}, "workflow_dispatch": {}}
    elif isinstance(trigger, dict):
        branches = trigger.get("branches", {})
        if isinstance(branches, dict):
            include = branches.get("include", [])
            on_trigger = {"push": {"branches": include}, "workflow_dispatch": {}}
        elif isinstance(branches, list):
            on_trigger = {"push": {"branches": branches}, "workflow_dispatch": {}}
    else:
        on_trigger = {"push": {"branches": ["main"]}, "workflow_dispatch": {}}

    # Runner mapping
    pool = data.get("pool", {})
    runs_on = "ubuntu-latest"
    if isinstance(pool, dict):
        vm_image = pool.get("vmImage")
        if vm_image:
            runs_on = vm_image
    elif isinstance(pool, str):
        runs_on = pool

    # Pass 1: Build job mapping for dependsOn resolution
    job_mapping = {}
    stages = data.get("stages")
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            stage_name = stage.get("stage", "stage").lower().replace(" ", "_").replace("-", "_")
            jobs = stage.get("jobs")
            if isinstance(jobs, list):
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    job_name_raw = job.get("job", "job")
                    job_name = f"{stage_name}_{job_name_raw.lower().replace(' ', '_').replace('-', '_')}"
                    job_mapping[job_name_raw] = job_name
                    job_mapping[job_name_raw.lower()] = job_name
    elif "jobs" in data and isinstance(data["jobs"], list):
        for job in data["jobs"]:
            if not isinstance(job, dict):
                continue
            job_name_raw = job.get("job", "job")
            job_name = job_name_raw.lower().replace(" ", "_").replace("-", "_")
            job_mapping[job_name_raw] = job_name
            job_mapping[job_name_raw.lower()] = job_name

    gha_jobs = {}

    # Case A: stages
    if isinstance(stages, list):
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            stage_name = stage.get("stage", "stage").lower().replace(" ", "_").replace("-", "_")
            jobs = stage.get("jobs")
            if isinstance(jobs, list):
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    job_name_raw = job.get("job", "job")
                    job_name = f"{stage_name}_{job_name_raw.lower().replace(' ', '_').replace('-', '_')}"
                    
                    depends_on = job.get("dependsOn")
                    needs = []
                    if depends_on:
                        if isinstance(depends_on, str):
                            needs = [job_mapping.get(depends_on, job_mapping.get(depends_on.lower(), depends_on))]
                        elif isinstance(depends_on, list):
                            needs = [job_mapping.get(d, job_mapping.get(d.lower(), d)) for d in depends_on]

                    steps_list = job.get("steps", [])
                    gha_steps = []
                    
                    has_checkout_none = False
                    for step in steps_list:
                        if isinstance(step, dict) and "checkout" in step and step["checkout"] == "none":
                            has_checkout_none = True
                            break
                    if not has_checkout_none:
                        gha_steps.append({
                            "name": "Checkout Code",
                            "uses": "actions/checkout@v4"
                        })

                    for step in steps_list:
                        if isinstance(step, dict):
                            gha_steps.extend(map_ado_step_to_gha(step))

                    gha_jobs[job_name] = {
                        "runs-on": runs_on,
                        "steps": gha_steps
                    }
                    if needs:
                        gha_jobs[job_name]["needs"] = needs

    # Case B: jobs at root
    elif "jobs" in data and isinstance(data["jobs"], list):
        for job in data["jobs"]:
            if not isinstance(job, dict):
                continue
            job_name = job.get("job", "job").lower().replace(" ", "_").replace("-", "_")
            depends_on = job.get("dependsOn")
            needs = []
            if depends_on:
                if isinstance(depends_on, str):
                    needs = [job_mapping.get(depends_on, job_mapping.get(depends_on.lower(), depends_on))]
                elif isinstance(depends_on, list):
                    needs = [job_mapping.get(d, job_mapping.get(d.lower(), d)) for d in depends_on]

            steps_list = job.get("steps", [])
            gha_steps = []
            
            has_checkout_none = False
            for step in steps_list:
                if isinstance(step, dict) and "checkout" in step and step["checkout"] == "none":
                    has_checkout_none = True
                    break
            if not has_checkout_none:
                gha_steps.append({
                    "name": "Checkout Code",
                    "uses": "actions/checkout@v4"
                })

            for step in steps_list:
                if isinstance(step, dict):
                    gha_steps.extend(map_ado_step_to_gha(step))

            gha_jobs[job_name] = {
                "runs-on": runs_on,
                "steps": gha_steps
            }
            if needs:
                gha_jobs[job_name]["needs"] = needs

    # Case C: steps at root
    elif "steps" in data and isinstance(data["steps"], list):
        steps_list = data["steps"]
        gha_steps = []
        
        has_checkout_none = False
        for step in steps_list:
            if isinstance(step, dict) and "checkout" in step and step["checkout"] == "none":
                has_checkout_none = True
                break
        if not has_checkout_none:
            gha_steps.append({
                "name": "Checkout Code",
                "uses": "actions/checkout@v4"
            })

        for step in steps_list:
            if isinstance(step, dict):
                gha_steps.extend(map_ado_step_to_gha(step))

        gha_jobs["build"] = {
            "runs-on": runs_on,
            "steps": gha_steps
        }

    # Generate output YAML using PyYAML
    workflow = {
        "name": Path(rel_path).stem.replace("-", " ").replace("_", " ").title(),
        "on": on_trigger,
        "jobs": gha_jobs
    }

    import yaml as pyyaml
    class Dumper(pyyaml.SafeDumper):
        def increase_indent(self, flow=False, indentless=False):
            return super(Dumper, self).increase_indent(flow, False)
            
    header = (
        f"# Translated from Azure DevOps YAML Pipeline: {rel_path}\n"
        "# Replaces original ADO stages and tasks with native GitHub Actions equivalents.\n\n"
    )
    return header + pyyaml.dump(workflow, Dumper=Dumper, default_flow_style=False, sort_keys=False)


def translate_raw_yaml_pipeline(
    content: str,
    rel_path: str,
    prompt_manager: PromptManager,
    slm_service: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Translate raw Azure DevOps pipeline YAML file to GitHub Actions workflows."""
    if slm_service and slm_service.available:
        translation_rules = prompt_manager.get_prompt("05_yaml_translation.md")
        combined_prompt = (
            f"{translation_rules}\n\n"
            "Please translate the following Azure DevOps pipeline YAML file into GitHub Actions workflows/actions format. "
            "Output the result as a valid JSON dictionary matching the response schema with 'workflows', "
            "'reusable_workflows', and 'composite_actions' keys.\n\n"
            f"File Path: {rel_path}\n"
            f"YAML Content:\n{content}"
        )
        system_prompt = prompt_manager.get_prompt("00_system_prompt.md")
        try:
            raw_response = slm_service.generate_sync(combined_prompt, system_prompt=system_prompt)
            data = json.loads(raw_response)
            return data.get("workflows", [])
        except Exception:
            pass

    # Deterministic smart fallback
    wf_name = Path(rel_path).stem.replace("-", " ").replace("_", " ").title()
    target_wf_path = f".github/workflows/{Path(rel_path).stem.lower().replace(' ', '_')}.yml"
    
    workflow_content = parse_and_translate_ado_yaml(content, rel_path)

    return [
        {
            "name": f"{wf_name}-workflow",
            "file_path": target_wf_path,
            "content": workflow_content,
            "description": f"Generated workflow translation for Azure DevOps YAML pipeline {rel_path}.",
        }
    ]


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
                logger.info("No discovery data provided. Creating discovery metadata from the supplied repository scope.")
                generated_payload = build_example_input_payload(source, target)
                discovery_data = AdoDiscoveryData(**generated_payload["discovery_data"])

            # Ensure repository_url is set in the source context to preserve history
            if "repository_url" not in source:
                if discovery_data.repositories:
                    matching_repo = next(
                        (r for r in discovery_data.repositories if r.name == source["repository"]),
                        discovery_data.repositories[0]
                    )
                    source["repository_url"] = matching_repo.url
                else:
                    source["repository_url"] = f"https://dev.azure.com/{source['organization']}/{source['project']}/_git/{source['repository']}"

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

    async def execute(
        self,
        plan: Dict[str, Any],
        mode: str = "dry_run",
        output_dir: Optional[Union[str, Path]] = None,
        github_token: Optional[str] = None,
        create_remote: bool = False,
        remote_executor: Optional[Any] = None,
        source_repo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a dry-run or migrate workflow for the generated migration plan."""
        if plan.get("status") == "failed" or "migration_plan" not in plan:
            logger.error("Attempted to execute an invalid or failed migration plan.")
            return {"status": "failed", "error": "Invalid migration plan schema."}

        if mode == "migrate":
            target_dir = Path(output_dir or Path.cwd())
            target_dir.mkdir(parents=True, exist_ok=True)
            workflows_dir = target_dir / ".github" / "workflows"
            workflows_dir.mkdir(parents=True, exist_ok=True)

            created_files: List[str] = []
            generated_assets = plan.get("generated_assets", {})
            repo_name = plan["analysis"]["target"]["repository"].lower().replace(" ", "-")

            source_url = source_repo_url or plan.get("analysis", {}).get("source", {}).get("repository_url")
            temp_workspace = None
            clone_dir = None
            executor = remote_executor or GitHubRemoteExecutor(token=github_token)

            if source_url:
                temp_workspace = tempfile.TemporaryDirectory()
                clone_dir = Path(temp_workspace.name) / "repo"
                clone_dir.mkdir(parents=True, exist_ok=True)
                try:
                    executor.clone_repository(source_url, clone_dir)
                    logger.info(f"Cloned source repository from {source_url} to temporary workspace.")
                except Exception as exc:
                    logger.warning(f"Cloning source repository failed: {exc}")
                    clone_dir = None
                    if temp_workspace:
                        temp_workspace.cleanup()
                        temp_workspace = None

            # Scan cloned repository for Azure DevOps YAML pipeline files
            discovered_workflows = []
            if clone_dir:
                for path in clone_dir.rglob("*.y*ml"):
                    try:
                        if ".github/workflows" in str(path).replace("\\", "/"):
                            continue
                        content = path.read_text(encoding="utf-8")
                        if is_ado_pipeline_file(content):
                            rel_path = path.relative_to(clone_dir)
                            logger.info(f"Discovered Azure DevOps pipeline file: {rel_path}")
                            translated = translate_raw_yaml_pipeline(
                                content,
                                str(rel_path),
                                self._prompt_manager,
                                self._slm_service
                            )
                            discovered_workflows.extend(translated)
                    except Exception as e:
                        logger.warning(f"Failed to scan/translate pipeline file {path}: {e}")

            # Merge workflows
            all_workflows = list(generated_assets.get("workflows", []))
            for dw in discovered_workflows:
                if not any(w["file_path"] == dw["file_path"] for w in all_workflows):
                    all_workflows.append(dw)

            # Write workflow assets to target_dir (and clone_dir if available)
            for workflow in all_workflows:
                path = target_dir / workflow["file_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(workflow["content"], encoding="utf-8")
                created_files.append(str(path))

                if clone_dir:
                    clone_path = clone_dir / workflow["file_path"]
                    clone_path.parent.mkdir(parents=True, exist_ok=True)
                    clone_path.write_text(workflow["content"], encoding="utf-8")

            # Write other assets to target_dir (and clone_dir)
            for reusable in generated_assets.get("reusable_workflows", []):
                path = target_dir / reusable["file_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(reusable["content"], encoding="utf-8")
                created_files.append(str(path))
                if clone_dir:
                    c_path = clone_dir / reusable["file_path"]
                    c_path.parent.mkdir(parents=True, exist_ok=True)
                    c_path.write_text(reusable["content"], encoding="utf-8")

            for composite in generated_assets.get("composite_actions", []):
                path = target_dir / composite["file_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(composite["content"], encoding="utf-8")
                created_files.append(str(path))
                if clone_dir:
                    c_path = clone_dir / composite["file_path"]
                    c_path.parent.mkdir(parents=True, exist_ok=True)
                    c_path.write_text(composite["content"], encoding="utf-8")

            # Copy all repository content (excluding .git) from clone_dir to target_dir if available
            if clone_dir:
                for item in clone_dir.iterdir():
                    if item.name == ".git":
                        continue
                    destination = target_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, destination, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, destination)

            # Write reports to target_dir
            report_markdown = [
                "# Migration Report",
                "",
                f"- Source repository: {plan['analysis']['source']['repository']}",
                f"- Target repository: {plan['analysis']['target']['repository']}",
                f"- Validation status: {plan['validation']['overall_status']}",
                "",
                "## Generated files",
            ]
            for created_file in created_files:
                report_markdown.append(f"- {created_file}")
            report_markdown.extend([
                "",
                "## Recommendations",
            ])
            for recommendation in plan.get("recommendations", {}).get("risk_assessment", []):
                report_markdown.append(f"- {recommendation['description']}")

            markdown_path = target_dir / "migration_report.md"
            markdown_path.write_text("\n".join(report_markdown) + "\n", encoding="utf-8")
            json_path = target_dir / "migration_report.json"
            json_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

            remote_result = None
            if create_remote:
                try:
                    target_org = plan["analysis"]["target"]["organization"]
                    target_repo = plan["analysis"]["target"]["repository"]
                    repo_info = executor.create_repository(target_org, target_repo, private=True)
                    repo_url = repo_info.get("html_url") or f"https://github.com/{target_org}/{target_repo}"
                    repo_full_name = repo_info.get("full_name") or f"{target_org}/{target_repo}"

                    push_target = clone_dir if clone_dir else target_dir
                    push_result = executor.push_directory(push_target, repo_url)
                    remote_result = {
                        "status": "created",
                        "repository_url": repo_url,
                        "full_name": repo_full_name,
                        "push": push_result,
                    }
                    logger.info(f"Remote repository created and pushed to {repo_url}")
                except Exception as exc:
                    remote_result = {"status": "failed", "error": str(exc)}
                    logger.warning(f"Remote repository creation failed: {exc}")

            if temp_workspace:
                try:
                    temp_workspace.cleanup()
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary workspace: {e}")

            return {
                "status": "migrated",
                "message": "Local migration artifacts and reports were generated successfully.",
                "created_files": created_files,
                "reports": [str(markdown_path), str(json_path)],
                "remote_write": remote_result,
                "plan_summary": {
                    "source": plan["analysis"]["source"],
                    "target": plan["analysis"]["target"],
                    "total_steps": len(plan["migration_plan"]["steps"]),
                    "validation_status": plan["validation"]["overall_status"],
                },
            }

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
    parser.add_argument(
        "--example-input-output",
        help="Path to write a generated example input JSON file. Defaults to examples/example_input.json in the repository root.",
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "dry-run", "report", "migrate"],
        default="plan",
        help="Execution mode: plan generates the migration plan, dry-run validates it, report writes the report, and migrate writes local workflow assets and reports.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory used for local migrate output when --mode migrate is selected.",
    )
    parser.add_argument(
        "--github-token",
        help="GitHub token used for optional remote repository creation and push during migrate mode.",
    )
    parser.add_argument(
        "--create-remote",
        action="store_true",
        help="Create a remote GitHub repository and push the generated assets when migrate mode is used.",
    )
    parser.add_argument(
        "--slm-api-base",
        help="API base URL for local OpenAI-compatible SLM (e.g., http://localhost:11434/v1 for Ollama).",
    )
    parser.add_argument(
        "--slm-api-key",
        default="ollama",
        help="API key for local OpenAI-compatible SLM.",
    )
    parser.add_argument(
        "--slm-model",
        default="qwen2.5-coder:7b",
        help="Model name for local OpenAI-compatible SLM.",
    )
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
                data = json.load(f)
                if isinstance(data, dict) and "discovery_data" in data:
                    context["discovery_data"] = data["discovery_data"]
                else:
                    context["discovery_data"] = data
            logger.info(f"Loaded discovery data metadata from {args.discovery_file}")
        except Exception as e:
            logger.error(f"Failed to read discovery file: {e}")

    paths = resolve_migration_paths(
        context["source"],
        context["target"],
        output_dir=args.output_dir,
        example_input_output=args.example_input_output,
    )
    generated_payload = build_example_input_payload(context["source"], context["target"], discovery_data=context.get("discovery_data"))
    if args.mode == "plan" or args.example_input_output:
        written_path = write_example_input_file(paths["input_path"], context["source"], context["target"], discovery_data=context.get("discovery_data"))
        logger.info(f"Wrote generated input file to {written_path}")

    if "discovery_data" not in context:
        context["discovery_data"] = generated_payload["discovery_data"]

    agent = AdoGitHubMigrationAgent()
    if args.slm_api_base:
        logger.info(f"Using local SLM service at {args.slm_api_base} with model {args.slm_model}")
        local_slm = LocalSLMService(
            api_base=args.slm_api_base,
            model=args.slm_model,
            api_key=args.slm_api_key
        )
        agent.set_slm_service(local_slm)

    plan_res = asyncio.run(agent.plan("Plan migration", context))

    if args.mode == "plan":
        print(json.dumps(plan_res, indent=2))
        return

    if args.mode == "report":
        report_payload = {
            "status": "report_generated",
            "plan": plan_res,
            "report_path": str(Path(args.output_dir or Path.cwd()) / "migration_report.md") if args.output_dir else str(Path.cwd() / "migration_report.md"),
        }
        output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "migration_report.md"
        report_path.write_text(
            f"# Migration Report\n\n- Source repository: {plan_res['analysis']['source']['repository']}\n- Target repository: {plan_res['analysis']['target']['repository']}\n- Validation status: {plan_res['validation']['overall_status']}\n",
            encoding="utf-8",
        )
        print(json.dumps(report_payload, indent=2))
        return

    target_output_dir = Path(args.output_dir) if args.output_dir else paths["output_dir"]
    exec_res = asyncio.run(
        agent.execute(
            plan_res,
            mode=args.mode.replace("-", "_"),
            output_dir=target_output_dir,
            github_token=args.github_token,
            create_remote=args.create_remote,
            source_repo_url=plan_res.get("analysis", {}).get("source", {}).get("repository_url"),
        )
    )
    print(json.dumps(exec_res, indent=2))


if __name__ == "__main__":
    standalone_main()
