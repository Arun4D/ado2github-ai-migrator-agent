from ado2github_migrator.domain.models import MigrationRun


class InMemoryMigrationRunStore:
    """Development adapter. Replace with a SQLAlchemy/PostgreSQL adapter in production."""

    def __init__(self) -> None:
        self._runs: dict[str, MigrationRun] = {}

    def save(self, run: MigrationRun) -> None:
        self._runs[str(run.id)] = run

    def get(self, run_id: str) -> MigrationRun | None:
        return self._runs.get(run_id)
