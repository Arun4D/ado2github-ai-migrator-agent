from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from ado2github_migrator.application.service import MigrationService
from ado2github_migrator.domain.models import RepositoryRef
from ado2github_migrator.infrastructure.memory_store import InMemoryMigrationRunStore

app = FastAPI(title="ADO to GitHub Migrator", version="0.1.0")
service = MigrationService(InMemoryMigrationRunStore())


class CreateRunRequest(BaseModel):
    ado_organization: str = Field(min_length=1)
    ado_project: str = Field(min_length=1)
    ado_repository: str = Field(min_length=1)
    github_organization: str = Field(min_length=1)
    github_repository: str = Field(min_length=1)
    dry_run: bool = True


class RunResponse(BaseModel):
    id: str
    status: str
    dry_run: bool


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/migration-runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(request: CreateRunRequest) -> RunResponse:
    run = service.create_run(
        source=RepositoryRef(request.ado_organization, request.ado_repository, request.ado_project),
        target=RepositoryRef(request.github_organization, request.github_repository),
        dry_run=request.dry_run,
    )
    return RunResponse(id=str(run.id), status=run.status, dry_run=run.dry_run)


@app.post("/v1/migration-runs/{run_id}/analyze", response_model=RunResponse)
def analyze_run(run_id: str) -> RunResponse:
    try:
        run = service.mark_analyzed(run_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return RunResponse(id=str(run.id), status=run.status, dry_run=run.dry_run)
