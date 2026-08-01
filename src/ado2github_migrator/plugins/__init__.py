from typing import Protocol


class MigrationPlugin(Protocol):
    name: str
    version: str

    def register(self) -> None: ...
