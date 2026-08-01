from typing import Protocol


class ChatModel(Protocol):
    async def complete(self, prompt: str) -> str:
        """Return a structured recommendation; implementations must not log secrets."""


class SLMService(Protocol):
    """Subset of the external orchestrator service used by this plugin."""

    available: bool

    def classify_intent_sync(self, intent: str, choices: list[tuple[str, str]]) -> str: ...

    async def generate(self, prompt: str) -> str: ...
