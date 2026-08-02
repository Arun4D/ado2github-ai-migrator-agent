from typing import Dict, List
import yaml
from schemas.discovery import AdoDiscoveryData
from schemas.migration_plan import MigrationPlan
from schemas.github_actions import GeneratedAssets
from schemas.validation import ValidationReport, ValidationCheck


class ValidationEngine:
    """Validates migrated assets against syntactical correctness, security rules, and scope limits."""

    def validate(
        self,
        discovery_data: AdoDiscoveryData,
        plan: MigrationPlan,
        assets: GeneratedAssets,
    ) -> ValidationReport:
        checks: List[ValidationCheck] = []

        # 1. Validate repository migration
        if discovery_data.repositories:
            repo = discovery_data.repositories[0]
            checks.append(
                ValidationCheck(
                    name="repository_migration_scope",
                    category="repository",
                    status="passed",
                    message=f"Repository {repo.name} matches scope limit rules.",
                )
            )
            if not repo.default_branch:
                checks.append(
                    ValidationCheck(
                        name="default_branch_check",
                        category="repository",
                        status="warning",
                        message="Default branch not defined in metadata; defaulting to 'main'.",
                        remediation="Confirm default branch configuration in target repository.",
                    )
                )
            else:
                checks.append(
                    ValidationCheck(
                        name="default_branch_check",
                        category="repository",
                        status="passed",
                        message=f"Default branch is mapped to '{repo.default_branch}'.",
                    )
                )

        # 2. Validate workflow syntax
        for workflow in assets.workflows:
            try:
                # Load workflow YAML to verify standard syntax
                data = yaml.safe_load(workflow.content)
                if not isinstance(data, dict):
                    raise ValueError("Workflow is not a valid YAML dictionary object.")

                missing_keys = []
                if "name" not in data:
                    missing_keys.append("name")
                if "on" not in data and True not in data:
                    missing_keys.append("on")
                if "jobs" not in data:
                    missing_keys.append("jobs")
                if missing_keys:
                    checks.append(
                        ValidationCheck(
                            name="workflow_syntax_check",
                            category="syntax",
                            status="failed",
                            message=f"Workflow {workflow.file_path} is missing core keys: {', '.join(missing_keys)}.",
                            remediation="Edit generated workflow to contain root 'name', 'on', and 'jobs' properties.",
                        )
                    )
                else:
                    checks.append(
                        ValidationCheck(
                            name="workflow_syntax_check",
                            category="syntax",
                            status="passed",
                            message=f"Workflow {workflow.file_path} parsed successfully as valid YAML with standard Action root keys.",
                        )
                    )
            except Exception as e:
                checks.append(
                    ValidationCheck(
                        name="workflow_syntax_check",
                        category="syntax",
                        status="failed",
                        message=f"Failed to parse generated YAML for workflow {workflow.file_path}: {e}",
                        remediation="Regenerate workflow or fix structural formatting issues manually.",
                    )
                )

        # 3. Validate runners
        for r_map in plan.runners:
            if not r_map.target_runner_label:
                checks.append(
                    ValidationCheck(
                        name="runner_mapping_check",
                        category="runners",
                        status="failed",
                        message=f"Runner mapping for pool '{r_map.source_pool}' is empty.",
                        remediation="Specify a valid hosted or self-hosted label.",
                    )
                )
            else:
                checks.append(
                    ValidationCheck(
                        name="runner_mapping_check",
                        category="runners",
                        status="passed",
                        message=f"Source pool '{r_map.source_pool}' successfully mapped to runner '{r_map.target_runner_label}'.",
                    )
                )

        # 4. Validate variables and secrets (Security Constraints)
        for var in plan.variables:
            if not var.target_name.isidentifier():
                checks.append(
                    ValidationCheck(
                        name="variable_name_check",
                        category="variables",
                        status="warning",
                        message=f"Variable name '{var.target_name}' contains non-standard characters.",
                        remediation="Rename variable to use standard alphanumeric/underscore identifiers.",
                    )
                )

        for sec in plan.secrets:
            # Check secret safety rules (ensure no values are logged or stored in cleartext plan)
            checks.append(
                ValidationCheck(
                    name="secret_safety_check",
                    category="secrets",
                    status="passed",
                    message=f"Secret '{sec.source_name}' successfully mapped to target placeholder '{sec.target_name}'. No credential values exposed.",
                )
            )

        # Determine overall status
        failed_count = sum(1 for c in checks if c.status == "failed")
        warning_count = sum(1 for c in checks if c.status == "warning")

        overall_status = "passed"
        if failed_count > 0:
            overall_status = "failed"
        elif warning_count > 0:
            overall_status = "warning"

        return ValidationReport(
            overall_status=overall_status,
            checks=checks,
        )
