from typing import Protocol

from ado2github_migrator.domain.models import MigrationRun


class MigrationRunStore(Protocol):
    def save(self, run: MigrationRun) -> None: ...
    def get(self, run_id: str) -> MigrationRun | None: ...


class RepositoryDiscoveryPort(Protocol):
    async def discover(self, run: MigrationRun) -> dict: ...


class ModelProvider(Protocol):
    async def recommend(self, discovery: dict) -> dict: ...
