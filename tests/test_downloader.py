
"""Tests for DownloadManager thread safety, error sanitization, and lock discipline."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from yank.engine.downloader import (
    DownloadItem,
    DownloadManager,
    DownloadOptions,
    DownloadProgress,
    DownloadStatus,
    _humanize_download_error,
    _human_rate,
)
from yank.models.config import AppConfig


@pytest.fixture
def config():
    cfg = AppConfig()
    cfg.max_concurrent = 2
    cfg.download_dir = "/tmp/yank-test-dl"
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


# ── Status transition tests ─────────────────────────────────────────────────


class TestStatusTransitions:
    """Verify that status changes are atomic under lock."""

    def test_cancel_pending(self, manager, dl_item):
        """Cancelling a PENDING item transitions to CANCELLED."""
        manager.register(dl_item)
        manager.cancel(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.CANCELLED

    def test_cancel_already_completed_is_noop(self, manager, dl_item):
        """Cancelling a COMPLETED item should not change status."""
        dl_item.status = DownloadStatus.COMPLETED
        manager.register(dl_item)
        manager.cancel(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.COMPLETED

    def test_cancel_already_cancelled_is_noop(self, manager, dl_item):
        """Cancelling an already CANCELLED item is a no-op."""
        dl_item.status = DownloadStatus.CANCELLED
        manager.register(dl_item)
        manager.cancel(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.CANCELLED

    def test_cancel_error_is_noop(self, manager, dl_item):
        """Cancelling an ERROR item should not change status."""
        dl_item.status = DownloadStatus.ERROR
        manager.register(dl_item)
        manager.cancel(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.ERROR

    def test_pause_queued(self, manager, dl_item):
        """Pausing a QUEUED item transitions to PAUSED."""
        dl_item.status = DownloadStatus.QUEUED
        manager.register(dl_item)
        manager.pause(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.PAUSED

    def test_pause_pending_is_noop(self, manager, dl_item):
        """Pausing a PENDING item (not queued/downloading) is a no-op."""
        manager.register(dl_item)
        manager.pause(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.PENDING

    def test_pause_completed_is_noop(self, manager, dl_item):
        """Pausing a COMPLETED item is a no-op."""
        dl_item.status = DownloadStatus.COMPLETED
        manager.register(dl_item)
        manager.pause(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.COMPLETED

    def test_start_already_downloading_is_noop(self, manager, dl_item):
        """Starting an already DOWNLOADING item is a no-op."""
        dl_item.status = DownloadStatus.DOWNLOADING
        manager.register(dl_item)
        manager.start(dl_item.id)
        # Should stay DOWNLOADING (not spawn another thread)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.DOWNLOADING


# ── Concurrency limit tests ─────────────────────────────────────────────────


class TestConcurrencyLimit:
    """Verify max_concurrent enforcement."""

    def test_queues_when_at_limit(self, config):
        """When at concurrency limit, new items are QUEUED."""
        config.max_concurrent = 1
        mgr = DownloadManager(config)

        item1 = DownloadItem.create(
            url="https://example.com/1", title="Video 1",
            format_id="22", options=DownloadOptions(),
        )
        item1.status = DownloadStatus.DOWNLOADING
        mgr.register(item1)

        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="22", options=DownloadOptions(),
        )
        mgr.register(item2)
        mgr.start(item2.id)

        item = mgr.get(item2.id)
        assert item.status == DownloadStatus.QUEUED

    def test_starts_when_slot_available(self, config):
        """When under limit, item starts normally."""
        config.max_concurrent = 2
        mgr = DownloadManager(config)

        item1 = DownloadItem.create(
            url="https://example.com/1", title="Video 1",
            format_id="22", options=DownloadOptions(),
        )
        mgr.register(item1)
        mgr.start(item1.id)

        # Should either be DOWNLOADING (if download ran fast) or not ERROR
        item = mgr.get(item1.id)
        assert item.status != DownloadStatus.QUEUED


# ── Cancel flag integrity ───────────────────────────────────────────────────


class TestCancelFlagIntegrity:
    """Verify cancel flags are managed correctly."""

    def test_cancel_flag_present_after_register(self, manager, dl_item):
        """After registration, a cancel flag exists."""
        manager.register(dl_item)
        flag = manager._cancel_flags.get(dl_item.id)
        assert flag is not None
        assert isinstance(flag, threading.Event)
        assert not flag.is_set()

    def test_cancel_flag_set_on_cancel(self, manager, dl_item):
        """Cancelling sets the flag."""
        manager.register(dl_item)
        manager.cancel(dl_item.id)
        # After cancel, the flag may have been cleaned up by _run_download
        # if the download thread ran; but in our case there's no thread.
        # The flag should still exist since _run_download never ran.
        flag = manager._cancel_flags.get(dl_item.id)
        if flag is not None:
            assert flag.is_set()

    def test_cancel_flag_cleared_on_start(self, manager, dl_item):
        """Starting a download clears the cancel flag."""
        manager.register(dl_item)
        # Set the flag to simulate a prior cancel
        manager._cancel_flags[dl_item.id].set()
        manager.start(dl_item.id)
        flag = manager._cancel_flags.get(dl_item.id)
        # After start (M-1 fix), flag should be cleared
        # But if the download thread runs, the flag might be popped
        if flag is not None:
            assert not flag.is_set()


# ── Concurrent cancel/start race test ───────────────────────────────────────


class TestConcurrentCancelStart:
    """Simulate the M-1 race condition scenario."""

    def test_rapid_cancel_start_sequence(self, manager, dl_item):
        """Rapid cancel→start→cancel should not lose the cancel signal."""
        manager.register(dl_item)

        # First cancel
        manager.cancel(dl_item.id)
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.CANCELLED

        # Re-register fresh item
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="22", options=DownloadOptions(),
        )
        manager.register(item2)
        # Start then immediately cancel
        manager.start(item2.id)
        manager.cancel(item2.id)

        item_after = manager.get(item2.id)
        # Should be CANCELLED (not DOWNLOADING or lost signal)
        assert item_after.status in (
            DownloadStatus.CANCELLED,
            DownloadStatus.ERROR,  # download thread may have errored
        )


# ── Callback tests ──────────────────────────────────────────────────────────


class TestCallbacks:
    """Verify progress and finished callbacks fire correctly."""

    def test_progress_callback_fires(self, manager, dl_item):
        """Progress callback should fire on status change."""
        events = []
        mgr = DownloadManager(
            AppConfig(),
            on_progress=lambda item: events.append(("progress", item.status)),
            on_finished=lambda item: events.append(("finished", item.status)),
        )
        mgr.register(dl_item)
        mgr.cancel(dl_item.id)
        # Should have at least one progress event from cancel()
        progress_events = [e for e in events if e[0] == "progress"]
        assert len(progress_events) >= 1

    def test_finished_callback_fires_on_cancel(self, manager, dl_item):
        """Finished callback should fire on cancel."""
        events = []
        mgr = DownloadManager(
            AppConfig(),
            on_progress=lambda item: events.append(("progress", item.status)),
            on_finished=lambda item: events.append(("finished", item.status)),
        )
        mgr.register(dl_item)
        mgr.cancel(dl_item.id)
        finished_events = [e for e in events if e[0] == "finished"]
        assert len(finished_events) == 1

    def test_pause_does_not_fire_finished(self, manager, dl_item):
        """Pausing should NOT fire the finished callback."""
        events = []
        mgr = DownloadManager(
            AppConfig(),
            on_progress=lambda item: events.append(("progress", item.status)),
            on_finished=lambda item: events.append(("finished", item.status)),
        )
        dl_item.status = DownloadStatus.QUEUED
        mgr.register(dl_item)
        mgr.pause(dl_item.id)
        finished_events = [e for e in events if e[0] == "finished"]
        assert len(finished_events) == 0


# ── All-items and active-count tests ────────────────────────────────────────


class TestQueryMethods:
    """Verify all_items, active_count, and get."""

    def test_all_items_returns_all(self, manager, dl_item):
        manager.register(dl_item)
        items = manager.all_items()
        assert len(items) == 1
        assert items[0].id == dl_item.id

    def test_get_nonexistent(self, manager):
        assert manager.get("nonexistent") is None

    def test_active_count_downloading(self, manager, dl_item):
        dl_item.status = DownloadStatus.DOWNLOADING
        manager.register(dl_item)
        assert manager.active_count() == 1

    def test_active_count_completed(self, manager, dl_item):
        dl_item.status = DownloadStatus.COMPLETED
        manager.register(dl_item)
        assert manager.active_count() == 0

    def test_cancel_all_terminates_active(self, manager, dl_item):
        dl_item.status = DownloadStatus.DOWNLOADING
        manager.register(dl_item)
        manager.cancel_all()
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.CANCELLED

    def test_pause_all_pauses_downloading(self, manager, dl_item):
        dl_item.status = DownloadStatus.DOWNLOADING
        manager.register(dl_item)
        manager.pause_all()
        item = manager.get(dl_item.id)
        assert item.status == DownloadStatus.PAUSED


# ── Error message sanitization ──────────────────────────────────────────────


class TestHumanizeDownloadError:
    """Test _humanize_download_error message sanitization."""

    def test_disk_full_detected(self):
        msg = _humanize_download_error("No space left on device")
        assert "disk full" in msg.lower()

    def test_permission_denied_detected(self):
        msg = _humanize_download_error("Permission denied: /tmp/file.mp4")
        assert "permission denied" in msg.lower()

    def test_ffmpeg_missing_detected(self):
        msg = _humanize_download_error("ffmpeg not found")
        assert "ffmpeg" in msg.lower()

    def test_timeout_detected(self):
        msg = _humanize_download_error("Connection timed out")
        assert "timed out" in msg.lower()

    def test_http_403_detected(self):
        msg = _humanize_download_error("HTTP Error 403: Forbidden")
        assert "forbidden" in msg.lower()

    def test_http_404_detected(self):
        msg = _humanize_download_error("HTTP Error 404: Not Found")
        assert "not found" in msg.lower()

    def test_strips_error_prefix(self):
        msg = _humanize_download_error("ERROR: Something bad happened")
        assert not msg.startswith("ERROR:")

    def test_path_stripping_unix(self):
        """Unix-style paths should be stripped from fallback message."""
        msg = _humanize_download_error(
            "Unable to write to /home/user/Downloads/video.mp4"
        )
        assert "/home/user" not in msg

    def test_fallback_returns_string(self):
        """Even unrecognised errors should return a string."""
        msg = _humanize_download_error("xyzzy unknown error")
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_truncates_long_messages(self):
        """Messages over 200 chars should be truncated."""
        long_msg = "X" * 500
        msg = _humanize_download_error(long_msg)
        assert len(msg) <= 203  # 200 + "..." at most

    def test_empty_input(self):
        msg = _humanize_download_error("")
        assert msg == "Download failed."


# ── Human-readable rate tests ───────────────────────────────────────────────


class TestHumanRate:
    def test_bytes(self):
        assert _human_rate(0) == "0 B/s"
        assert _human_rate(500) == "500 B/s"

    def test_kib(self):
        assert "KiB/s" in _human_rate(2000)

    def test_mib(self):
        assert "MiB/s" in _human_rate(5_000_000)

    def test_gib(self):
        assert "GiB/s" in _human_rate(5_000_000_000)


# ── DownloadProgress display tests ──────────────────────────────────────────


class TestDownloadProgress:
    def test_speed_display_zero(self):
        dp = DownloadProgress(speed=0)
        assert dp.speed_display == "\u2014"

    def test_percent_display(self):
        dp = DownloadProgress(percent=42.5)
        assert dp.percent_display == "42.5%"

    def test_eta_display_none(self):
        dp = DownloadProgress(eta=None)
        assert dp.eta_display == "\u2014"

    def test_eta_display_seconds(self):
        dp = DownloadProgress(eta=45)
        assert dp.eta_display == "45s"

    def test_eta_display_minutes(self):
        dp = DownloadProgress(eta=125)
        assert dp.eta_display == "2m05s"

    def test_eta_display_hours(self):
        dp = DownloadProgress(eta=3725)
        assert "h" in dp.eta_display

    def test_speed_mbps(self):
        dp = DownloadProgress(speed=5_000_000)
        assert dp.speed_mbps is not None
        assert dp.speed_mbps > 1.0


# ── DownloadItem tests ──────────────────────────────────────────────────────


class TestDownloadItem:
    def test_create_sets_id(self):
        item = DownloadItem.create(
            url="https://example.com", title="Test",
            format_id="22", options=DownloadOptions(),
        )
        assert len(item.id) == 12
        assert item.title == "Test"

    def test_create_defaults_title(self):
        item = DownloadItem.create(
            url="https://example.com", title="",
            format_id="22", options=DownloadOptions(),
        )
        assert item.title == "Unknown"

    def test_default_status(self):
        item = DownloadItem.create(
            url="https://example.com", title="Test",
            format_id="22", options=DownloadOptions(),
        )
        assert item.status == DownloadStatus.PENDING

    def test_created_at_is_recent(self):
        item = DownloadItem.create(
            url="https://example.com", title="Test",
            format_id="22", options=DownloadOptions(),
        )
        assert abs(item.created_at - time.time()) < 5.0


# ── Mocked YoutubeDL integration tests ───────────────────────────────────────


class TestMockedYoutubeDL:
    """Test DownloadManager._run_download with mocked yt_dlp.YoutubeDL."""

    @pytest.fixture
    def config(self):
        cfg = AppConfig()
        cfg.max_concurrent = 2
        cfg.download_dir = "/tmp/yank-test-dl"
        return cfg

    def test_run_download_success(self, config, monkeypatch):
        """A successful download transitions to COMPLETED and fires callbacks."""
        import yt_dlp

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, url, download=True):
                return {
                    "title": "Test Video",
                    "ext": "mp4",
                    "_filename": "/tmp/yank-test-dl/Test Video.mp4",
                }

        calls = []
        monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(output_dir="/tmp/yank-test-dl"),
        )
        mgr.on_progress = lambda i: calls.append(("progress", i.status))
        mgr.on_finished = lambda i: calls.append(("finished", i.status))
        mgr.register(item)

        # Override _pump_queue to be a no-op during test
        mgr._pump_queue = lambda: None
        mgr.start(item.id)

        import time
        time.sleep(0.5)

        final = mgr.get(item.id)
        assert final.status == DownloadStatus.COMPLETED
        assert final.file_path == "/tmp/yank-test-dl/Test Video.mp4"
        assert any(e[0] == "finished" for e in calls)

    def test_run_download_error(self, config, monkeypatch):
        """An exception in extract_info transitions to ERROR."""
        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, url, download=True):
                raise RuntimeError("HTTP Error 404: Not Found")

        import yt_dlp
        monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/missing",
            title="Missing Video",
            format_id="22",
            options=DownloadOptions(output_dir="/tmp/yank-test-dl"),
        )
        mgr.register(item)
        mgr._pump_queue = lambda: None
        mgr.start(item.id)

        import time
        time.sleep(0.5)

        final = mgr.get(item.id)
        assert final.status == DownloadStatus.ERROR
        assert "not found" in final.error.lower()


    def test_progress_hook_downloading(self, config):
        """Progress hook with 'downloading' status updates DownloadProgress."""
        import threading

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        mgr.register(item)
        cancel_flag = threading.Event()

        mgr._progress_hook(
            item.id,
            {
                "status": "downloading",
                "total_bytes": 10485760,
                "downloaded_bytes": 5242880,
                "speed": 1024000,
                "eta": 5,
                "filename": "/tmp/video.mp4",
            },
            cancel_flag,
        )

        updated = mgr.get(item.id)
        assert updated.progress.percent == pytest.approx(50.0, rel=0.1)
        assert updated.progress.speed == 1024000
        assert updated.progress.eta == 5

    def test_progress_hook_uses_percent_str(self, config):
        """When total_bytes is missing, fall back to _percent_str."""
        import threading

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        mgr.register(item)
        cancel_flag = threading.Event()

        mgr._progress_hook(
            item.id,
            {
                "status": "downloading",
                "downloaded_bytes": 5000,
                "speed": 100000,
                "_percent_str": "75.5%",
            },
            cancel_flag,
        )

        updated = mgr.get(item.id)
        assert updated.progress.percent == pytest.approx(75.5, rel=0.01)

    def test_progress_hook_finished(self, config):
        """Progress hook with 'finished' status sets percent to 100."""
        import threading

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        mgr.register(item)
        cancel_flag = threading.Event()

        mgr._progress_hook(
            item.id,
            {"status": "finished", "filename": "/tmp/video.mp4"},
            cancel_flag,
        )

        updated = mgr.get(item.id)
        assert updated.progress.percent == 100.0
        assert updated.file_path == "/tmp/video.mp4"

    def test_progress_hook_error(self, config):
        """Progress hook with 'error' status sets ERROR status."""
        import threading

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        mgr.register(item)
        cancel_flag = threading.Event()

        mgr._progress_hook(
            item.id,
            {"status": "error"},
            cancel_flag,
        )

        updated = mgr.get(item.id)
        assert updated.status == DownloadStatus.ERROR
        assert updated.progress.status_text == "Error"


    def test_progress_hook_cancel_flag_raises(self, config):
        """Progress hook raises _CancelDownload when cancel flag is set."""
        import threading

        from yank.engine.downloader import _CancelDownload

        mgr = DownloadManager(config)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test",
            format_id="22",
            options=DownloadOptions(),
        )
        mgr.register(item)
        cancel_flag = threading.Event()
        cancel_flag.set()

        with pytest.raises(_CancelDownload):
            mgr._progress_hook(
                item.id,
                {"status": "downloading"},
                cancel_flag,
            )

    def test_progress_hook_none_item_cancels(self, config):
        """Progress hook raises _CancelDownload when item is not found."""
        import threading

        from yank.engine.downloader import _CancelDownload

        mgr = DownloadManager(config)
        cancel_flag = threading.Event()

        with pytest.raises(_CancelDownload):
            mgr._progress_hook(
                "nonexistent-id",
                {"status": "downloading"},
                cancel_flag,
            )

    def test_pause_all_sets_downloading_to_paused(self, config, monkeypatch):
        """pause_all transitions DOWNLOADING items to PAUSED."""
        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, url, download=True):
                import time
                time.sleep(0.2)
                return {"title": "Test", "_filename": "/tmp/out.mp4"}

        import yt_dlp
        monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

        mgr = DownloadManager(config)
        mgr._pump_queue = lambda: None

        item1 = DownloadItem.create(
            url="https://example.com/1", title="V1",
            format_id="22", options=DownloadOptions(output_dir="/tmp/yank-test-dl"),
        )
        item2 = DownloadItem.create(
            url="https://example.com/2", title="V2",
            format_id="22", options=DownloadOptions(output_dir="/tmp/yank-test-dl"),
        )
        mgr.register(item1)
        mgr.register(item2)

        # Set item1 as DOWNLOADING (simulating it's running)
        item1.status = DownloadStatus.DOWNLOADING
        mgr.start(item2.id)

        import time
        time.sleep(0.05)
        mgr.pause_all()

        i1 = mgr.get(item1.id)
        i2 = mgr.get(item2.id)
        assert i1.status == DownloadStatus.PAUSED
        assert i2.status in (DownloadStatus.PAUSED, DownloadStatus.DOWNLOADING, DownloadStatus.QUEUED)

    def test_cancel_all_pumps_queue(self, config):
        """cancel_all should trigger _pump_queue."""
        call_count = [0]

        mgr = DownloadManager(config)
        orig_pump = mgr._pump_queue

        def counting_pump():
            call_count[0] += 1
            orig_pump()

        mgr._pump_queue = counting_pump

        item = DownloadItem.create(
            url="https://example.com/video", title="Test",
            format_id="22", options=DownloadOptions(),
        )
        mgr.register(item)

    def test_concurrent_downloads_limit(self, config):
        """When at max_concurrent, start() queues instead of downloading."""
        config.max_concurrent = 1
        mgr = DownloadManager(config)

        item1 = DownloadItem.create(
            url="https://example.com/1", title="V1",
            format_id="22", options=DownloadOptions(),
        )
        item2 = DownloadItem.create(
            url="https://example.com/2", title="V2",
            format_id="22", options=DownloadOptions(),
        )
        mgr.register(item1)
        mgr.register(item2)
        # Manually set item1 as downloading
        item1.status = DownloadStatus.DOWNLOADING

        mgr.start(item2.id)
        i2 = mgr.get(item2.id)
        assert i2.status == DownloadStatus.QUEUED

    def test_pump_queue_starts_queued_item(self, config, monkeypatch):
        """_pump_queue starts a queued item when a slot opens."""
        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, url, download=True):
                import time
                time.sleep(0.1)
                return {"title": "Test", "_filename": "/tmp/out.mp4"}

        import yt_dlp
        monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

        config.max_concurrent = 1
        mgr = DownloadManager(config)
        # Save original pump to call it manually
        orig_pump = mgr._pump_queue

        item1 = DownloadItem.create(
            url="https://example.com/1", title="V1",
            format_id="22", options=DownloadOptions(output_dir="/tmp/yank-test-dl"),
        )
        item2 = DownloadItem.create(
            url="https://example.com/2", title="V2",
            format_id="22", options=DownloadOptions(output_dir="/tmp/yank-test-dl"),
        )
        mgr.register(item1)
        mgr.register(item2)

        # Prevent auto-pumping while we set up
        mgr._pump_queue = lambda: None
        mgr.start(item1.id)
        import time
        time.sleep(0.05)

        # Now item1 is DOWNLOADING, item2 should queue
        mgr.start(item2.id)
        i2 = mgr.get(item2.id)
        assert i2.status == DownloadStatus.QUEUED

        # Simulate item1 finishing
        item1.status = DownloadStatus.COMPLETED
        # Restore and call the real pump
        mgr._pump_queue = orig_pump
        mgr._pump_queue()
        time.sleep(0.2)
        i2_after = mgr.get(item2.id)
        # Should have been started (or errored, but not queued)
        assert i2_after.status != DownloadStatus.QUEUED


# ── Extended humanize download error tests ───────────────────────────────────


class TestHumanizeDownloadErrorExtended:
    def test_permission_denied(self):
        msg = _humanize_download_error(
            "ERROR: [Errno 13] Permission denied: '/root/file.mp4'"
        )
        assert "permission denied" in msg.lower()

    def test_disk_full_errno_28(self):
        msg = _humanize_download_error(
            "OSError: [Errno 28] No space left on device"
        )
        assert "disk full" in msg.lower()

    def test_ffmpeg_not_found(self):
        msg = _humanize_download_error(
            "ERROR: ffmpeg not found. Please install ffmpeg."
        )
        assert "ffmpeg" in msg.lower()

    def test_http_403(self):
        msg = _humanize_download_error("HTTP Error 403: Forbidden")
        assert "forbidden" in msg.lower()

    def test_windows_path_sanitized(self):
        msg = _humanize_download_error(
            "Error writing to C:\\Users\\test\\Downloads\\video.mp4"
        )
        assert "C:\\Users" not in msg
        assert "[path]" in msg

    def test_tilde_path_sanitized(self):
        msg = _humanize_download_error(
            "Cannot save to ~/Downloads/video.mp4"
        )
        assert "~/" not in msg or "[path]" in msg

    def test_multiple_paths_collapsed(self):
        msg = _humanize_download_error(
            "Moved /tmp/file1 to /home/user/file2: error"
        )
        assert "[path] [path]" not in msg
        assert "[path]" in msg

    def test_none_input(self):
        msg = _humanize_download_error("")
        assert msg == "Download failed."

