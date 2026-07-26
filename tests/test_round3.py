
"""Tests for round-3 audit fixes: cancel_flag=None, start_all sync, created_at, ytdlp.config."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from yank.engine.downloader import (
    DownloadItem,
    DownloadManager,
    DownloadOptions,
    DownloadStatus,
)
from yank.engine.queue import QueueEngine


# ── C1: cancel_flag None handling ─────────────────────────────────────────


class TestCancelFlagNone:
    """C1: _run_download sets ERROR when cancel_flag is unexpectedly None."""

    def test_run_download_without_register_sets_error(self):
        """If cancel_flag is missing (item not registered), download should error."""
        mgr = DownloadManager.__new__(DownloadManager)
        mgr.config = type("C", (), {"download_dir": "/tmp", "max_concurrent": 1})()
        mgr._items = {}
        mgr._cancel_flags = {}
        mgr._threads = {}
        mgr._ydl_instances = {}
        mgr._lock = __import__("threading").Lock()

        events = []
        mgr.on_progress = lambda item: events.append(("progress", item.status))
        mgr.on_finished = lambda item: events.append(("finished", item.status))

        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        item.id = "test-c1-id"
        # Add to _items but NOT to _cancel_flags
        mgr._items[item.id] = item
        mgr._cancel_flags.pop(item.id, None)

        mgr._run_download(item.id)

        assert item.status == DownloadStatus.ERROR
        assert "state lost" in item.error.lower()
        # Should have called both callbacks
        finished_events = [e for e in events if e[0] == "finished"]
        assert len(finished_events) >= 1


# ── C2: start_all() no longer writes di.status unsynchronized ─────────────


class TestStartAllThreadSafety:
    """C2: start_all() delegates status handling to manager.start()."""

    def test_start_all_no_direct_status_write(self):
        """Verify start_all source doesn't directly assign di.status."""
        source = Path("src/yank/engine/queue.py").read_text()
        # The start_all method should NOT contain 'di.status ='
        # (it was removed in the C2 fix)
        in_start_all = False
        for line in source.splitlines():
            if "def start_all" in line:
                in_start_all = True
            elif in_start_all and line.strip().startswith("def "):
                in_start_all = False
            elif in_start_all and "di.status =" in line:
                pytest.fail(
                    f"start_all() still has unsynchronized di.status write: {line.strip()}"
                )

    def test_start_all_pending_calls_manager_start(self):
        """start_all() should call manager.start() for pending items."""
        config = type("C", (), {"download_dir": "/tmp", "max_concurrent": 2})()
        mgr = DownloadManager(config)

        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        item.status = DownloadStatus.PENDING
        mgr.register(item)

        from yank.engine.queue import QueueItem as QI

        qe = QueueEngine(config, mgr, path=Path("/tmp/nonexistent-queue.json"))
        qe._items = [QI.from_download_item(item)]

        qe.start_all()
        # After start_all, item should have been started
        di = mgr.get(item.id)
        assert di is not None
        # Either DOWNLOADING or ERROR (if yt-dlp missing / dir issue)
        assert di.status != DownloadStatus.PENDING


# ── C3: created_at falsy value bug ────────────────────────────────────────


class TestCreatedAtFalsyValue:
    """C3: created_at=0 is preserved, not replaced with time.time()."""

    def test_created_at_zero_preserved(self):
        """created_at=0 should NOT be replaced by current time."""
        config = type("C", (), {"download_dir": "/tmp", "max_concurrent": 1})()
        mgr = DownloadManager(config)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [{
                "id": "test-zero",
                "url": "https://example.com",
                "title": "Test",
                "format_id": "22",
                "created_at": 0,
            }]
            path.write_text(json.dumps(data))

            qe = QueueEngine(config, mgr, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 1
            assert items[0].created_at == 0.0

    def test_created_at_null_defaults_to_now(self):
        """created_at=null should default to current time."""
        config = type("C", (), {"download_dir": "/tmp", "max_concurrent": 1})()
        mgr = DownloadManager(config)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [{
                "id": "test-null",
                "url": "https://example.com",
                "title": "Test",
                "format_id": "22",
                "created_at": None,
            }]
            path.write_text(json.dumps(data))

            qe = QueueEngine(config, mgr, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 1
            # Should be recent, not 0
            assert items[0].created_at > 1000000000  # Some time after 2001

    def test_created_at_missing_defaults_to_now(self):
        """Missing created_at key should default to current time."""
        config = type("C", (), {"download_dir": "/tmp", "max_concurrent": 1})()
        mgr = DownloadManager(config)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [{
                "id": "test-missing",
                "url": "https://example.com",
                "title": "Test",
                "format_id": "22",
            }]
            path.write_text(json.dumps(data))

            qe = QueueEngine(config, mgr, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 1
            assert items[0].created_at > 1000000000


# ── C4: ytdlp.config updated on save ──────────────────────────────────────


class TestYtdlpConfigUpdate:
    """C4: Settings _save updates self.app.ytdlp.config reference."""

    def test_ytdlp_config_line_exists(self):
        """Verify the ytdlp.config update line exists in _save()."""
        source = Path("src/yank/screens/settings.py").read_text()
        assert "self._app.ytdlp.config = cfg" in source


# ── C5: max_concurrent ValueError surfaced ────────────────────────────────


class TestConcurrencySelectError:
    """C5: Invalid concurrency value shows error, doesn't silently ignore."""

    def test_concurrency_error_is_valueerror_not_bare_except(self):
        """The except clause should be ValueError, not bare Exception."""
        source = Path("src/yank/screens/settings.py").read_text()
        in_try_block = False
        for line in source.splitlines():
            if "cfg.max_concurrent = int(str(conc))" in line:
                in_try_block = True
            elif in_try_block and "except" in line:
                assert "ValueError" in line, (
                    f"Expected ValueError, got: {line.strip()}"
                )
                break
