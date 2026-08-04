import threading
from pathlib import Path
from typing import Dict, Optional

PROMPT_DIR = Path(__file__).parent / "prompts"


class PromptCache:
    """Thread-safe memory cache for loaded prompt templates."""

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._cache[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class PromptLoader:
    """Responsible for loading prompt markdown content from the filesystem."""

    def __init__(self, prompt_dir: Path, cache: Optional[PromptCache] = None) -> None:
        self.prompt_dir = prompt_dir
        self.cache = cache or PromptCache()

    def load_prompt(self, filename: str) -> str:
        """Load prompt content from filename, using cache if available."""
        cached_val = self.cache.get(filename)
        if cached_val is not None:
            return cached_val

        file_path = self.prompt_dir / filename
        if not file_path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        self.cache.set(filename, content)
        return content


class PromptManager:
    """Orchestrates formatting and rendering of modular system instructions."""

    def __init__(self, loader: PromptLoader) -> None:
        self.loader = loader

    def get_prompt(self, name: str) -> str:
        """Retrieve raw prompt contents by filename/key."""
        return self.loader.load_prompt(name)

    def format_prompt(self, name: str, variables: Dict[str, str]) -> str:
        """Retrieve prompt contents and replace placeholder formatting tokens."""
        content = self.get_prompt(name)
        for key, value in variables.items():
            content = content.replace(f"{{{key}}}", value)
        return content


# Backwards compatibility constants
_cache = PromptCache()
_loader = PromptLoader(PROMPT_DIR, _cache)

SYSTEM_PROMPT = _loader.load_prompt("00_system_prompt.md")
DISCOVERY_PROMPT = _loader.load_prompt("01_discovery.md")
GIT_REPOSITORY_PROMPT = _loader.load_prompt("02_git_repository.md")
BUILD_PIPELINE_PROMPT = _loader.load_prompt("03_build_pipeline.md")
RELEASE_PIPELINE_PROMPT = _loader.load_prompt("04_release_pipeline.md")
YAML_TRANSLATION_PROMPT = _loader.load_prompt("05_yaml_translation.md")
VARIABLES_PROMPT = _loader.load_prompt("06_variables.md")
SECRETS_PROMPT = _loader.load_prompt("07_secrets.md")
ENVIRONMENTS_PROMPT = _loader.load_prompt("08_environments.md")
RUNNER_MAPPING_PROMPT = _loader.load_prompt("09_runner_mapping.md")
VALIDATION_PROMPT = _loader.load_prompt("10_validation.md")
REPORTING_PROMPT = _loader.load_prompt("11_reporting.md")
ROLLBACK_PROMPT = _loader.load_prompt("12_rollback.md")
PLUGIN_FRAMEWORK_PROMPT = _loader.load_prompt("13_plugin_framework.md")
ACTUAL_MIGRATE_PROMPT = _loader.load_prompt("14_actual_migrate.md")