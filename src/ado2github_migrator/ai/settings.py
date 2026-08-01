from dataclasses import dataclass
from os import getenv


DEFAULT_QWEN_CODER_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"


@dataclass(frozen=True)
class QwenCoderSettings:
    """Configuration for vLLM, Ollama-compatible gateways, or other OpenAI APIs."""

    model: str = DEFAULT_QWEN_CODER_MODEL
    base_url: str = "http://localhost:8000/v1"
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 4096

    @classmethod
    def from_environment(cls) -> "QwenCoderSettings":
        return cls(
            model=getenv("MIGRATOR_LLM_MODEL", DEFAULT_QWEN_CODER_MODEL),
            base_url=getenv("MIGRATOR_LLM_BASE_URL", "http://localhost:8000/v1").rstrip("/"),
            api_key=getenv("MIGRATOR_LLM_API_KEY"),
            temperature=float(getenv("MIGRATOR_LLM_TEMPERATURE", "0.1")),
            max_tokens=int(getenv("MIGRATOR_LLM_MAX_TOKENS", "4096")),
        )
