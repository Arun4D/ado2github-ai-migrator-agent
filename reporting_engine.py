from typing import List
from schemas.discovery import AdoDiscoveryData
from schemas.migration_plan import MigrationPlan
from schemas.github_actions import GeneratedAssets
from schemas.validation import ValidationReport
from schemas.report import (
    MigrationReport,
    ExecutiveSummary,
    TechnicalSummary,
    UnsupportedFeature,
    RiskItem,
    RollbackStep,
)


class ReportingEngine:
    """Assembles validation, planning, and conversion summaries into comprehensive reports."""

    def generate_report(
        self,
        discovery_data: AdoDiscoveryData,
        plan: MigrationPlan,
        validation: ValidationReport,
        assets: GeneratedAssets,
    ) -> MigrationReport:
        # Determine completeness ratio
        total_steps = len(plan.steps)
        completed_steps = sum(1 for s in plan.steps if s.status == "completed")
        completeness = (completed_steps / total_steps) if total_steps > 0 else 1.0

        # Scan for unsupported elements in discovery data
        unsupported: List[UnsupportedFeature] = []
        for pipe in discovery_data.pipelines:
            if pipe.type == "classic_release":
                unsupported.append(
                    UnsupportedFeature(
                        feature_name="Classic Release Pipelines",
                        location=f"Pipeline {pipe.name}",
                        description="Classic Release UI Pipelines are translated to GitHub Actions CD workflows.",
                        impact="info",
                        recommendation="Verify migrated environments, deployment protection rules, and manual approvals in GitHub.",
                    )
                )

        # Risk assessment
        risks: List[RiskItem] = []
        if len(plan.secrets) > 0:
            risks.append(
                RiskItem(
                    category="security",
                    severity="medium",
                    description=f"{len(plan.secrets)} secrets are required. Direct credential values are not migrated.",
                    mitigation="Configure values manually in target GitHub Action repository secrets before executing workflows.",
                )
            )

        for r_map in plan.runners:
            if r_map.runner_type == "self_hosted":
                risks.append(
                    RiskItem(
                        category="runtime",
                        severity="high",
                        description=f"Self-hosted runner pool '{r_map.source_pool}' is required for builds.",
                        mitigation="Deploy Actions Runner Controller (ARC) or provision VM runner instances and register with GitHub runner group.",
                    )
                )

        # Standard Rollback Steps
        rollback_plan = [
            RollbackStep(
                order=1,
                action="Delete generated workflows",
                description="Remove workflow YAML files from target repository branch .github/workflows/.",
                verification_step="Verify .github/workflows directory is clean or reverted to original branch commit.",
            ),
            RollbackStep(
                order=2,
                action="Clean target configurations",
                description="Delete environment entries, repository variables, and secret mappings created during the execution.",
                verification_step="Check repository settings UI to verify clean state.",
            ),
            RollbackStep(
                order=3,
                action="Archive GitHub repository",
                description="If the target repository was newly created, delete or rename it to free the namespace.",
                verification_step="Verify target URL returns 404.",
            ),
        ]

        # Executive & Technical Summaries
        files_created = [w.file_path for w in assets.workflows] + [
            c.file_path for c in assets.composite_actions
        ]
        
        exec_summary = ExecutiveSummary(
            summary=(
                f"Migration plan created for repository mapping '{plan.mapping.source_repo}' -> '{plan.mapping.target_repo}'. "
                f"Overall validation status ended with: {validation.overall_status.upper()}."
            ),
            migration_completeness_ratio=completeness,
            risk_summary=(
                f"Identified {len(risks)} migration risks. "
                "Security secrets and self-hosted runners require manual intervention."
            ),
        )

        tech_summary = TechnicalSummary(
            total_pipelines_converted=len(discovery_data.pipelines),
            variables_mapped_count=len(plan.variables),
            secrets_mapped_count=len(plan.secrets),
            runners_mapped_count=len(plan.runners),
            files_created=files_created,
        )

        return MigrationReport(
            executive_summary=exec_summary,
            technical_summary=tech_summary,
            unsupported_features=unsupported,
            risk_assessment=risks,
            rollback_plan=rollback_plan,
        )
