"""Plugin loader and hook registry for yank.

Plugins are Python files in ~/.config/yank/plugins/ that define a
``register(app)`` or ``register(api)`` callable. Errors are logged and
never crash startup.

Hook API (minimal):
    api.on("download_finished", callback)
    api.add_command(name, callback, help_text)
    api.log(message)
"""

from __future__ import annotations

import importlib.util
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from yank.logging import get_logger
from yank.paths import CONFIG_DIR

_logger = get_logger(__name__)

PLUGIN_DIR = CONFIG_DIR / "plugins"


class PluginAPI:
    """Facade handed to plugins."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._hooks: dict[str, list[Callable[[Any], None]]] = defaultdict(list)
        self._commands: list[tuple[str, Callable[[], None], str]] = []

    def on(self, event: str, callback: Callable[[Any], None]) -> None:
        self._hooks[event].append(callback)

    def emit(self, event: str, payload: Any = None) -> None:
        for cb in list(self._hooks.get(event, ())):
            try:
                cb(payload)
            except Exception:
                _logger.debug("Plugin hook %s failed", event, exc_info=True)

    def add_command(self, name: str, callback: Callable[[], None], help_text: str = "") -> None:
        self._commands.append((name, callback, help_text))

    def commands(self) -> list[tuple[str, Callable[[], None], str]]:
        return list(self._commands)

    def log(self, message: str) -> None:
        _logger.info("plugin: %s", message)


def load_plugins(app: Any) -> tuple[int, PluginAPI]:
    """Load and register plugins. Returns (count, api)."""
    api = PluginAPI(app)
    if not PLUGIN_DIR.exists():
        return 0, api
    count = 0
    for path in sorted(PLUGIN_DIR.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"yank_plugin_{path.stem}", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if callable(register):
                try:
                    register(api)
                except TypeError:
                    register(app)
                count += 1
        except Exception:
            _logger.debug("Failed to load plugin %s", path, exc_info=True)
    return count, api
