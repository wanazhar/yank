"""Minimal plugin loader for yank.

Plugins are Python files in ~/.config/yank/plugins/ that define a
``register(app)`` callable. Errors are logged and never crash startup.
"""

from __future__ import annotations

import importlib.util

from yank.logging import get_logger
from yank.paths import CONFIG_DIR

_logger = get_logger(__name__)

PLUGIN_DIR = CONFIG_DIR / "plugins"


def load_plugins(app: object) -> int:
    """Load and register plugins. Returns count loaded."""
    if not PLUGIN_DIR.exists():
        return 0
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
                register(app)
                count += 1
        except Exception:
            _logger.debug("Failed to load plugin %s", path, exc_info=True)
    return count
