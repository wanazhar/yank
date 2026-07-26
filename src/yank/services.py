"""Lightweight services container shared across screens.

Avoids every screen reaching through ``self.app.*`` for config, history, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yank.engine.downloader import DownloadManager
    from yank.engine.queue import QueueEngine
    from yank.engine.updater import YtDlpManager
    from yank.models.config import AppConfig
    from yank.models.history import HistoryStore


@dataclass
class AppServices:
    """Thin bag of shared runtime objects owned by ``YankApp``.

    Mutated *only* by ``YankApp``; screens treat it as read-only config +
    manager handles.
    """

    config: AppConfig
    history: HistoryStore
    manager: DownloadManager
    queue: QueueEngine
    ytdlp: YtDlpManager
