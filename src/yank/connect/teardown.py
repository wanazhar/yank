"""Tear down downloads, queue, and staging when Connect stops."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from yank.connect.paths import CONNECT_QUEUE_PATH, CONNECT_STAGING_DIR
from yank.connect.state import clear_state
from yank.logging import get_logger

if TYPE_CHECKING:
    from yank.connect.runtime import ConnectRuntime

_logger = get_logger(__name__)


def wipe_staging(staging_dir: Path = CONNECT_STAGING_DIR) -> None:
    if not staging_dir.is_dir():
        return
    for entry in staging_dir.iterdir():
        try:
            if entry.is_file() or entry.is_symlink():
                entry.unlink(missing_ok=True)
            elif entry.is_dir():
                shutil.rmtree(entry)
        except OSError:
            _logger.debug("Failed to remove staging entry %s", entry, exc_info=True)


def clear_connect_queue_file(path: Path = CONNECT_QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]\n", encoding="utf-8")


def teardown_runtime(runtime: ConnectRuntime) -> None:
    """Cancel active work and drop queue + staging for Connect."""
    try:
        runtime.manager.cancel_all()
    except Exception:
        _logger.debug("cancel_all failed during connect teardown", exc_info=True)

    for qi in list(runtime.queue.get_items()):
        try:
            runtime.queue.remove(qi.id)
        except Exception:
            _logger.debug("queue remove failed for %s", qi.id, exc_info=True)

    try:
        runtime.queue.save()
    except Exception:
        _logger.debug("queue save failed during connect teardown", exc_info=True)

    wipe_staging(runtime.staging_dir)
    runtime.cookie_jar.clear_all()


def teardown_connect_disk() -> None:
    """Best-effort cleanup when the server process is already gone."""
    wipe_staging()
    clear_connect_queue_file()
    clear_state()
