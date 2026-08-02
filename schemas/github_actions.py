from typing import List, Optional
from pydantic import BaseModel, Field


class GeneratedWorkflow(BaseModel):
    name: str
    file_path: str  # e.g. .github/workflows/ci.yml
    content: str
    is_reusable: bool = False
    description: str


class GeneratedCompositeAction(BaseModel):
    name: str
    file_path: str  # e.g. .github/actions/custom-task/action.yml
    content: str
    description: str


class GeneratedAssets(BaseModel):
    workflows: List[GeneratedWorkflow] = Field(default_factory=list)
    reusable_workflows: List[GeneratedWorkflow] = Field(default_factory=list)
    composite_actions: List[GeneratedCompositeAction] = Field(default_factory=list)
    explanation: Optional[str] = None
