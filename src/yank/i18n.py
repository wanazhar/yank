"""Lightweight i18n helper for yank."""

from __future__ import annotations

import json
from typing import Any

from textual.widgets import Button as _Button
from textual.widgets import Checkbox as _Checkbox
from textual.widgets import Label as _Label

from yank.logging import get_logger
from yank.paths import CONFIG_DIR

_logger = get_logger(__name__)

_LOCALES: dict[str, dict[str, str]] = {
    "en": {},
}

_current = "en"


def set_language(lang: str) -> None:
    global _current
    _current = lang or "en"
    _load_locale(_current)


def _load_locale(lang: str) -> None:
    if _LOCALES.get(lang):
        return
    path = CONFIG_DIR / "locales" / f"{lang}.json"
    if path.exists():
        try:
            _LOCALES[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _LOCALES[lang] = {}
    else:
        _LOCALES[lang] = {}


def t(key: str, **kwargs: object) -> str:
    """Translate *key*, falling back to the key itself."""
    table = _LOCALES.get(_current, {})
    value = table.get(key, key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value


class LocalizedLabel(_Label):
    """Translate label text using the active locale."""

    def __init__(self, content="", *args, **kwargs):
        super().__init__(t(content) if isinstance(content, str) else content, *args, **kwargs)

    def update(self, content: Any = "", *, layout: bool = True) -> None:
        super().update(t(content) if isinstance(content, str) else content, layout=layout)


class LocalizedButton(_Button):
    """Translate button captions using the active locale."""

    def __init__(self, label=None, *args, **kwargs):
        kwargs.setdefault("flat", True)
        kwargs.setdefault("compact", True)
        super().__init__(t(label) if isinstance(label, str) else label, *args, **kwargs)


class LocalizedCheckbox(_Checkbox):
    """Translate checkbox captions using the active locale."""

    def __init__(self, label="", *args, **kwargs):
        super().__init__(t(label) if isinstance(label, str) else label, *args, **kwargs)
