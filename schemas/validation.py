from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ValidationCheck(BaseModel):
    name: str
    category: str  # repository, pipeline, variables, secrets, runners, syntax
    status: str  # passed, failed, warning
    message: str
    remediation: Optional[str] = Field(default=None, description="Suggested fix if check failed/warned")


class ValidationReport(BaseModel):
    overall_status: str  # passed, failed, warning
    checks: List[ValidationCheck] = Field(default_factory=list)
    validated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
