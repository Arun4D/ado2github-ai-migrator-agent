"""Deterministic utilities exposed with the migration plugin."""

from typing import Any


def validate_repository_scope(context: dict[str, Any]) -> list[str]:
    """Return required repository scope fields missing from an agent context."""
    source = context.get("source", {})
    target = context.get("target", {})
    missing = [key for key in ("organization", "project", "repository") if not source.get(key)]
    missing.extend(f"target.{key}" for key in ("organization", "repository") if not target.get(key))
    return missing
