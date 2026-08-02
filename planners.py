import json
from typing import Any, Dict, List, Optional
from prompts import PromptManager
from schemas.discovery import AdoDiscoveryData, AdoPipeline
from schemas.migration_plan import (
    RepoMapping,
    MigrationStep,
    VariableMapping,
    SecretMapping,
    RunnerMapping,
    EnvironmentMapping,
)
from schemas.github_actions import GeneratedAssets, GeneratedWorkflow, GeneratedCompositeAction


class GitRepoPlanner:
    """Handles Git repository migration planning (branches, tags, submodules, policies)."""

    def __init__(self, prompt_manager: PromptManager) -> None:
        self.prompt_manager = prompt_manager

    def plan(
        self,
        discovery_data: AdoDiscoveryData,
        target_org: str,
        target_repo: str,
        slm_service: Optional[Any] = None,
    ) -> RepoMapping:
        # Default mapping logic
        source_repo = discovery_data.repositories[0].name if discovery_data.repositories else "repo-default"
        return RepoMapping(
            source_org=discovery_data.organization,
            source_project=discovery_data.project,
            source_repo=source_repo,
            target_org=target_org,
            target_repo=target_repo,
        )


class PipelinePlanner:
    """Generates translation recommendations and targets for pipeline tasks."""

    def __init__(self, prompt_manager: PromptManager) -> None:
        self.prompt_manager = prompt_manager

    def plan(
        self,
        pipeline: AdoPipeline,
        slm_service: Optional[Any] = None,
    ) -> GeneratedAssets:
        if slm_service and slm_service.available:
            prompt = self.prompt_manager.format_prompt(
                "05_yaml_translation.md",
                {"pipeline_json": pipeline.model_dump_json(indent=2)},
            )
            system_prompt = self.prompt_manager.get_prompt("00_system_prompt.md")
            try:
                raw_response = slm_service.generate_sync(prompt, system_prompt=system_prompt)
                data = json.loads(raw_response)
                # Ensure structure matches GeneratedAssets
                workflows = [GeneratedWorkflow(**w) for w in data.get("workflows", [])]
                reusable = [GeneratedWorkflow(**w) for w in data.get("reusable_workflows", [])]
                composite = [GeneratedCompositeAction(**c) for c in data.get("composite_actions", [])]
                return GeneratedAssets(
                    workflows=workflows,
                    reusable_workflows=reusable,
                    composite_actions=composite,
                    explanation=data.get("explanation"),
                )
            except Exception:
                pass  # Fallback to deterministic template below

        # Deterministic default translation
        workflow_content = (
            f"# Translated from Azure DevOps Pipeline: {pipeline.name}\n"
            "name: CI Pipeline\n\n"
            "on:\n"
            "  push:\n"
            "    branches:\n"
            "      - main\n\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout Code\n"
            "        uses: actions/checkout@v4\n"
        )
        for stage in pipeline.stages:
            workflow_content += f"      # Stage: {stage.name}\n"
            for job in stage.jobs:
                workflow_content += f"      # Job: {job.get('name', 'unnamed')}\n"

        return GeneratedAssets(
            workflows=[
                GeneratedWorkflow(
                    name=f"{pipeline.name}-workflow",
                    file_path=f".github/workflows/{pipeline.name.lower().replace(' ', '_')}.yml",
                    content=workflow_content,
                    description=f"Generated workflow translation for Azure DevOps pipeline {pipeline.name}.",
                )
            ]
        )


class VariableSecretPlanner:
    """Plans mapping of pipeline variables and secrets (KeyVault references, Secure Files)."""

    def __init__(self, prompt_manager: PromptManager) -> None:
        self.prompt_manager = prompt_manager

    def plan(
        self,
        discovery_data: AdoDiscoveryData,
        slm_service: Optional[Any] = None,
    ) -> tuple[List[VariableMapping], List[SecretMapping]]:
        variables: List[VariableMapping] = []
        secrets: List[SecretMapping] = []

        # Process standard variables
        for var in discovery_data.variables:
            target_scope = "repository"
            if var.source == "environment":
                target_scope = "environment"
            
            if var.is_secret:
                secrets.append(
                    SecretMapping(
                        source_name=var.name,
                        target_name=var.name.upper().replace(" ", "_").replace("-", "_"),
                        target_scope=target_scope,
                        mapping_strategy="Repository Secret",
                    )
                )
            else:
                variables.append(
                    VariableMapping(
                        source_name=var.name,
                        target_name=var.name.upper().replace(" ", "_").replace("-", "_"),
                        target_scope=target_scope,
                    )
                )

        # Process secret metadata
        for sec in discovery_data.secrets_metadata:
            mapping_strategy = "Repository Secret"
            if sec.classification == "KeyVaultReference":
                mapping_strategy = "OIDC"
            secrets.append(
                SecretMapping(
                    source_name=sec.name,
                    target_name=sec.name.upper().replace(" ", "_").replace("-", "_"),
                    target_scope="repository",
                    mapping_strategy=mapping_strategy,
                )
            )

        return variables, secrets


class RunnerPlanner:
    """Determines GitHub Actions runner mapping recommendations based on ADO pool specs."""

    def __init__(self, prompt_manager: PromptManager) -> None:
        self.prompt_manager = prompt_manager

    def plan(
        self,
        discovery_data: AdoDiscoveryData,
        slm_service: Optional[Any] = None,
    ) -> List[RunnerMapping]:
        mappings: List[RunnerMapping] = []
        for pool in discovery_data.agent_pools:
            target_label = "ubuntu-latest"
            runner_type = "github_hosted"
            reason = "Standard pool mapped to default GitHub-hosted runner."

            if pool.os_type.lower() == "windows":
                target_label = "windows-latest"
                reason = "Windows build agents mapped to GitHub Windows hosted runner."
            elif pool.os_type.lower() == "macos":
                target_label = "macos-latest"
                reason = "macOS build agents mapped to GitHub macOS hosted runner."

            if not pool.is_hosted:
                target_label = f"self-hosted-{pool.name.lower().replace(' ', '-')}"
                runner_type = "self_hosted"
                reason = f"Self-hosted pool '{pool.name}' mapped to self-hosted runner matching pool label."

            mappings.append(
                RunnerMapping(
                    source_pool=pool.name,
                    target_runner_label=target_label,
                    runner_type=runner_type,
                    recommendation_reason=reason,
                )
            )
        
        # If no pools discovered, provide a default mapping recommendation
        if not mappings:
            mappings.append(
                RunnerMapping(
                    source_pool="Default Pool",
                    target_runner_label="ubuntu-latest",
                    runner_type="github_hosted",
                    recommendation_reason="No explicit agent pool discovered; defaulting to GitHub-hosted Linux runner.",
                )
            )
        return mappings


class EnvironmentPlanner:
    """Maps ADO environments and approval checks to GitHub environments."""

    def __init__(self, prompt_manager: PromptManager) -> None:
        self.prompt_manager = prompt_manager

    def plan(
        self,
        discovery_data: AdoDiscoveryData,
        slm_service: Optional[Any] = None,
    ) -> List[EnvironmentMapping]:
        mappings: List[EnvironmentMapping] = []
        for env in discovery_data.environments:
            has_approvals = len(env.approvals) > 0
            checks = [str(chk.get("type", "unknown")) for chk in env.checks]
            mappings.append(
                EnvironmentMapping(
                    source_name=env.name,
                    target_name=env.name.lower().replace(" ", "-"),
                    approvals_required=has_approvals,
                    checks_mapped=checks,
                )
            )
        return mappings
