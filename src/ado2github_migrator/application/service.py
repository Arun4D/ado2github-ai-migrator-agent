from ado2github_migrator.application.ports import MigrationRunStore
from ado2github_migrator.domain.models import MigrationRun, RepositoryRef, RunStatus


class MigrationService:
    def __init__(self, store: MigrationRunStore) -> None:
        self._store = store

    def create_run(self, source: RepositoryRef, target: RepositoryRef, dry_run: bool = True) -> MigrationRun:
        if not source.project:
            raise ValueError("Azure DevOps project is required for the source repository")
        run = MigrationRun(source=source, target=target, dry_run=dry_run)
        self._store.save(run)
        return run

    def mark_analyzed(self, run_id: str) -> MigrationRun:
        run = self._required(run_id)
        run.transition_to(RunStatus.ANALYZED)
        self._store.save(run)
        return run

    def _required(self, run_id: str) -> MigrationRun:
        run = self._store.get(run_id)
        if run is None:
            raise KeyError(f"Migration run not found: {run_id}")
        return run
