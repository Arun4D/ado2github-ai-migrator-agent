from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AdoRepository(BaseModel):
    name: str
    id: str
    url: str
    default_branch: str
    branches: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    has_lfs: bool = False
    submodules: List[str] = Field(default_factory=list)


class AdoVariable(BaseModel):
    name: str
    value: Optional[str] = None
    is_secret: bool = False
    source: str = "pipeline"  # pipeline or group


class AdoSecretMetadata(BaseModel):
    name: str
    classification: str  # e.g., PAT, KeyVaultReference, Certificate
    has_value: bool = False


class AdoStage(BaseModel):
    name: str
    jobs: List[Dict[str, Any]] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)


class AdoPipeline(BaseModel):
    name: str
    id: int
    type: str  # "yaml", "classic_build", "classic_release"
    variables: List[AdoVariable] = Field(default_factory=list)
    stages: List[AdoStage] = Field(default_factory=list)
    triggers: List[Dict[str, Any]] = Field(default_factory=list)
    schedules: List[Dict[str, Any]] = Field(default_factory=list)


class AdoAgentPool(BaseModel):
    name: str
    is_hosted: bool = False
    agent_count: int = 0
    os_type: str = "Linux"  # Linux, Windows, macOS


class AdoEnvironment(BaseModel):
    name: str
    approvals: List[Dict[str, Any]] = Field(default_factory=list)
    checks: List[Dict[str, Any]] = Field(default_factory=list)


class AdoServiceConnection(BaseModel):
    name: str
    id: str
    type: str  # e.g., AzureRM, GitHub, DockerRegistry
    auth_type: str  # ServicePrincipal, PAT, OAuth


class AdoDiscoveryData(BaseModel):
    organization: str
    project: str
    repositories: List[AdoRepository] = Field(default_factory=list)
    pipelines: List[AdoPipeline] = Field(default_factory=list)
    variables: List[AdoVariable] = Field(default_factory=list)
    secrets_metadata: List[AdoSecretMetadata] = Field(default_factory=list)
    agent_pools: List[AdoAgentPool] = Field(default_factory=list)
    environments: List[AdoEnvironment] = Field(default_factory=list)
    service_connections: List[AdoServiceConnection] = Field(default_factory=list)
