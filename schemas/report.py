from typing import List, Optional
from pydantic import BaseModel, Field


class UnsupportedFeature(BaseModel):
    feature_name: str
    location: str  # e.g. pipeline name, stage name, task name
    description: str
    impact: str  # blocking, degraded, alternative_mapped
    recommendation: str


class RiskItem(BaseModel):
    category: str  # e.g., security, runtime, compatibility
    severity: str  # high, medium, low
    description: str
    mitigation: str


class RollbackStep(BaseModel):
    order: int
    action: str
    description: str
    verification_step: str


class ExecutiveSummary(BaseModel):
    summary: str
    migration_completeness_ratio: float
    risk_summary: str


class TechnicalSummary(BaseModel):
    total_pipelines_converted: int
    variables_mapped_count: int
    secrets_mapped_count: int
    runners_mapped_count: int
    files_created: List[str] = Field(default_factory=list)


class MigrationReport(BaseModel):
    executive_summary: ExecutiveSummary
    technical_summary: TechnicalSummary
    unsupported_features: List[UnsupportedFeature] = Field(default_factory=list)
    risk_assessment: List[RiskItem] = Field(default_factory=list)
    rollback_plan: List[RollbackStep] = Field(default_factory=list)
