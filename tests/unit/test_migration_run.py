import pytest

from ado2github_migrator.domain.models import MigrationRun, RepositoryRef, RunStatus


def test_non_dry_run_requires_approval_before_migration():
    run = MigrationRun(
        source=RepositoryRef("ado", "source", "project"),
        target=RepositoryRef("github", "target"),
        dry_run=False,
    )
    run.transition_to(RunStatus.ANALYZED)
    run.transition_to(RunStatus.PLANNED)

    with pytest.raises(ValueError, match="approved"):
        run.transition_to(RunStatus.MIGRATING)


def test_approved_non_dry_run_can_migrate():
    run = MigrationRun(
        source=RepositoryRef("ado", "source", "project"),
        target=RepositoryRef("github", "target"),
        dry_run=False,
        approved=True,
    )
    run.transition_to(RunStatus.ANALYZED)
    run.transition_to(RunStatus.PLANNED)
    run.transition_to(RunStatus.MIGRATING)

    assert run.status is RunStatus.MIGRATING
