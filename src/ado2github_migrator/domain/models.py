from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4


class RunStatus(StrEnum):
    DISCOVERING = "discovering"
    ANALYZED = "analyzed"
    PLANNED = "planned"
    MIGRATING = "migrating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class RepositoryRef:
    organization: str
    repository: str
    project: str | None = None


@dataclass
class MigrationRun:
    source: RepositoryRef
    target: RepositoryRef
    dry_run: bool = True
    id: UUID = field(default_factory=uuid4)
    status: RunStatus = RunStatus.DISCOVERING
    approved: bool = False

    def transition_to(self, next_status: RunStatus) -> None:
        allowed = {
            RunStatus.DISCOVERING: {RunStatus.ANALYZED, RunStatus.FAILED, RunStatus.CANCELLED},
            RunStatus.ANALYZED: {RunStatus.PLANNED, RunStatus.FAILED, RunStatus.CANCELLED},
            RunStatus.PLANNED: {RunStatus.MIGRATING, RunStatus.CANCELLED},
            RunStatus.MIGRATING: {RunStatus.VALIDATING, RunStatus.FAILED, RunStatus.ROLLED_BACK},
            RunStatus.VALIDATING: {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.ROLLED_BACK},
        }
        if next_status not in allowed.get(self.status, set()):
            raise ValueError(f"Invalid run transition: {self.status} -> {next_status}")
        if next_status is RunStatus.MIGRATING and (self.dry_run or not self.approved):
            raise ValueError("Migration requires a non-dry-run, approved plan")
        self.status = next_status
