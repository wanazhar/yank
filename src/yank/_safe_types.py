"""Safe type-coercion helpers shared across queue and history deserialization.

Extracted from ``yank.engine.queue`` and ``yank.models.history`` to avoid
duplication.
"""

from __future__ import annotations

from typing import Any


def _coerce_str_list(value: Any) -> list[str]:
    """Coerce a value to ``list[str]`` for safe deserialization."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return []


def _coerce_optional_str(value: Any) -> str | None:
    """Coerce a value to ``str | None`` for safe deserialization."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_float(value: Any, default: float) -> float:
    """Coerce a value to ``float`` with fallback."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    """Coerce a value to ``int`` with fallback."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
