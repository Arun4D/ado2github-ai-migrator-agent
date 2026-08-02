from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RepoMapping(BaseModel):
    source_org: str
    source_project: str
    source_repo: str
    target_org: str
    target_repo: str


class MigrationStep(BaseModel):
    id: str
    phase: str  # e.g., discovery, translation, mapping, validation, execution
    name: str
    description: str
    status: str = "planned"  # planned, in_progress, completed, failed


class VariableMapping(BaseModel):
    source_name: str
    target_name: str
    target_scope: str  # repository, environment, organization
    environment_name: Optional[str] = Field(default=None, description="Only relevant if scope is environment")


class SecretMapping(BaseModel):
    source_name: str
    target_name: str
    target_scope: str  # repository, environment, organization
    environment_name: Optional[str] = Field(default=None, description="Only relevant if scope is environment")
    mapping_strategy: str  # e.g., OIDC, Repository Secret, manual_fill


class RunnerMapping(BaseModel):
    source_pool: str
    target_runner_label: str
    runner_type: str  # github_hosted, self_hosted
    recommendation_reason: str


class EnvironmentMapping(BaseModel):
    source_name: str
    target_name: str
    approvals_required: bool
    checks_mapped: List[str] = Field(default_factory=list)


class MigrationPlan(BaseModel):
    mapping: RepoMapping
    steps: List[MigrationStep] = Field(default_factory=list)
    variables: List[VariableMapping] = Field(default_factory=list)
    secrets: List[SecretMapping] = Field(default_factory=list)
    runners: List[RunnerMapping] = Field(default_factory=list)
    environments: List[EnvironmentMapping] = Field(default_factory=list)
    confidence_score: float = 1.0
    next_actions: List[str] = Field(default_factory=list)
