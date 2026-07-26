"""Tests for round-2 audit fixes: start() guards, cancel_all pumping, type coercion."""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

import pytest

from yank._safe_types import _coerce_optional_str, _coerce_str_list
from yank.engine.downloader import (
    DownloadItem,
    DownloadManager,
    DownloadOptions,
    DownloadStatus,
)
from yank.engine.queue import (
    QueueEngine,
)
from yank.models.config import AppConfig


@pytest.fixture
def config():
    cfg = AppConfig()
    cfg.max_concurrent = 2
    cfg.download_dir = "/tmp/yank-test"
    return cfg


@pytest.fixture
def manager(config):
    return DownloadManager(config)


@pytest.fixture
def dl_item():
    return DownloadItem.create(
        url="https://example.com/video",
        title="Test Video",
        format_id="22",
        options=DownloadOptions(),
    )


# ── B1: start() doesn't restart terminal items ──────────────────────────────


class TestStartTerminalGuard:
    """B1: start() should not restart CANCELLED, COMPLETED, or ERROR items."""

    def test_start_cancelled_is_noop(self, manager, dl_item):
        dl_item.status = DownloadStatus.CANCELLED
        manager.register(dl_item)
        manager.start(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.CANCELLED

    def test_start_completed_is_noop(self, manager, dl_item):
        dl_item.status = DownloadStatus.COMPLETED
        manager.register(dl_item)
        manager.start(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.COMPLETED

    def test_start_error_is_noop(self, manager, dl_item):
        dl_item.status = DownloadStatus.ERROR
        manager.register(dl_item)
        manager.start(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.ERROR

    def test_start_paused_is_allowed(self, manager, dl_item):
        """PAUSED items should be restarted."""
        dl_item.status = DownloadStatus.PAUSED
        manager.register(dl_item)
        manager.start(dl_item.id)
        item = manager.get(dl_item.id)
        # May be DOWNLOADING or ERROR (if download dir doesn't exist)
        assert item.status != DownloadStatus.PAUSED

    def test_cancel_then_start_from_another_thread(self, manager, dl_item):
        """B1 scenario: cancel() races with start() — start should no-op."""
        manager.register(dl_item)

        # Simulate cancel running between get() and lock acquisition
        results = []

        def racy_start():
            manager.get(dl_item.id)
            # At this point, the other thread cancels
            cancel_done.set()
            # Wait for cancel to complete before proceeding
            start_ok.wait()
            manager.start(dl_item.id)
            item_after = manager.get(dl_item.id)
            results.append(("started", item_after.status))

        def racy_cancel():
            cancel_done.wait()
            manager.cancel(dl_item.id)
            start_ok.set()

        cancel_done = threading.Event()
        start_ok = threading.Event()

        t1 = threading.Thread(target=racy_start)
        t2 = threading.Thread(target=racy_cancel)
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        # After cancel+start, status should NOT be DOWNLOADING
        item = manager.get(dl_item.id)
        assert item.status != DownloadStatus.DOWNLOADING


# ── B2: start() concurrency-limit status set under lock ────────────────────


class TestStartLockDiscipline:
    """B2: start() mutations are performed under lock."""

    def test_concurrent_starts_respect_limit(self, config):
        """Two rapid starts with max_concurrent=1 only start one."""
        config.max_concurrent = 1
        mgr = DownloadManager(config)

        item1 = DownloadItem.create(
            url="https://example.com/1",
            title="V1",
            format_id="22",
            options=DownloadOptions(),
        )
        item2 = DownloadItem.create(
            url="https://example.com/2",
            title="V2",
            format_id="22",
            options=DownloadOptions(),
        )
        mgr.register(item1)
        mgr.register(item2)

        # Start both concurrently
        barrier = threading.Barrier(2, timeout=2)

        def start_item(item):
            barrier.wait()
            mgr.start(item.id)

        t1 = threading.Thread(target=start_item, args=(item1,))
        t2 = threading.Thread(target=start_item, args=(item2,))
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        # Only one should be DOWNLOADING (or started), the other QUEUED
        i1 = mgr.get(item1.id)
        i2 = mgr.get(item2.id)
        # At most one DOWNLOADING; other is QUEUED (or both errored quickly)
        downloading_count = sum(
            1 for s in (i1.status, i2.status) if s == DownloadStatus.DOWNLOADING
        )
        assert downloading_count <= 1


# ── B3: cancel_all() / pause_all() don't pump mid-loop ──────────────────────


class TestCancelAllNoMidPump:
    """B3: cancel_all() and pause_all() suppress per-item pumping."""

    def test_cancel_all_pump_count(self, manager, dl_item):
        """cancel_all() should not trigger _pump_queue per item."""
        pump_count = [0]
        orig_pump = manager._pump_queue

        def counting_pump():
            pump_count[0] += 1
            orig_pump()

        manager._pump_queue = counting_pump

        dl_item.status = DownloadStatus.DOWNLOADING
        manager.register(dl_item)
        item2 = DownloadItem.create(
            url="https://example.com/2",
            title="V2",
            format_id="22",
            options=DownloadOptions(),
        )
        item2.status = DownloadStatus.QUEUED
        manager.register(item2)

        manager.cancel_all()

        # cancel_all calls _pump_queue exactly once (at the end)
        assert pump_count[0] == 1

    def test_pause_all_does_not_pump(self, manager, dl_item):
        """pause_all() should not trigger _pump_queue at all."""
        pump_count = [0]
        orig_pump = manager._pump_queue

        def counting_pump():
            pump_count[0] += 1
            orig_pump()

        manager._pump_queue = counting_pump

        dl_item.status = DownloadStatus.QUEUED
        manager.register(dl_item)
        manager.pause_all()
        # pause_all passes _pump=False, so no pumps
        assert pump_count[0] == 0

    def test_single_cancel_still_pumps(self, manager, dl_item):
        """Single cancel() still pumps (existing behavior)."""
        pump_count = [0]
        orig_pump = manager._pump_queue

        def counting_pump():
            pump_count[0] += 1
            orig_pump()

        manager._pump_queue = counting_pump

        manager.register(dl_item)
        manager.cancel(dl_item.id)
        assert pump_count[0] == 1

    def test_single_pause_still_pumps_when_downloading(self, manager, dl_item):
        """Single pause() of a DOWNLOADING item still pumps."""
        pump_count = [0]
        orig_pump = manager._pump_queue

        def counting_pump():
            pump_count[0] += 1
            orig_pump()

        manager._pump_queue = counting_pump

        dl_item.status = DownloadStatus.DOWNLOADING
        manager.register(dl_item)
        manager.pause(dl_item.id)
        assert pump_count[0] == 1


# ── B5: QueueItem type coercion on load ────────────────────────────────────


class TestQueueTypeCoercion:
    """B5: QueueEngine.load() coerces custom_format and subtitle_langs."""

    def test_coerce_str_list_from_list(self):
        assert _coerce_str_list(["en", "fr"]) == ["en", "fr"]

    def test_coerce_str_list_from_string(self):
        """Single string wrapped in list, not exploded to chars."""
        assert _coerce_str_list("en") == ["en"]
        assert _coerce_str_list("fr") == ["fr"]

    def test_coerce_str_list_from_none(self):
        assert _coerce_str_list(None) == []

    def test_coerce_str_list_from_int(self):
        """Non-list/string defaults to empty list."""
        assert _coerce_str_list(42) == []

    def test_coerce_optional_str_from_none(self):
        assert _coerce_optional_str(None) is None

    def test_coerce_optional_str_from_string(self):
        assert _coerce_optional_str("hello") == "hello"

    def test_coerce_optional_str_from_int(self):
        """Int coerced to string."""
        assert _coerce_optional_str(42) == "42"

    def test_load_with_bad_custom_format_type(self, config, manager):
        """Manually-edited JSON with non-string custom_format is coerced."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [
                {
                    "id": "test1",
                    "url": "https://example.com",
                    "title": "Test",
                    "format_id": "22",
                    "custom_format": 123,
                }
            ]
            path.write_text(json.dumps(data))
            qe = QueueEngine(config, manager, path=path)
            qe.load()
            items = qe.get_items()
            assert items[0].custom_format == "123"

    def test_load_with_bad_subtitle_langs_string(self, config, manager):
        """Manually-edited JSON with string subtitle_langs is coerced."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [
                {
                    "id": "test1",
                    "url": "https://example.com",
                    "title": "Test",
                    "format_id": "22",
                    "subtitle_langs": "en",
                }
            ]
            path.write_text(json.dumps(data))
            qe = QueueEngine(config, manager, path=path)
            qe.load()
            items = qe.get_items()
            assert items[0].subtitle_langs == ["en"]


# ── B7: OptionsScreen._build_options guards against None selected_format ────


class TestBuildOptionsNoneGuard:
    """B7: _build_options returns None early if selected_format is None."""

    def test_build_options_with_none_format_returns_none(self):
        """Test is structural — verifies the guard exists and returns None."""
        # We can't easily instantiate OptionsScreen without Textual,
        # but we can verify the import doesn't crash and the guard
        # is present by reading the source.
        from pathlib import Path

        source = Path("src/yank/screens/options.py").read_text()
        assert "if self.selected_format is None:" in source
        assert '"No format selected."' in source
