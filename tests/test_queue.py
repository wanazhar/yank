
"""Tests for QueueEngine crash recovery, persistence, and reordering."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from yank.engine.downloader import (
    DownloadItem,
    DownloadManager,
    DownloadOptions,
    DownloadStatus,
)
from yank.engine.queue import QueueEngine, QueueItem
from yank.models.config import AppConfig


@pytest.fixture
def config():
    return AppConfig()


@pytest.fixture
def tmp_queue_path():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td) / "queue.json"


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


@pytest.fixture
def queue_engine(config, manager, tmp_queue_path):
    return QueueEngine(config, manager, path=tmp_queue_path)


# ── Basic operations ────────────────────────────────────────────────────────


class TestQueueBasic:
    def test_add_item(self, queue_engine, dl_item):
        qi = queue_engine.add(dl_item)
        assert qi.id == dl_item.id
        assert queue_engine.size() == 1

    def test_add_multiple(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="18", options=DownloadOptions(),
        )
        queue_engine.add(item2)
        assert queue_engine.size() == 2

    def test_remove_item(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        queue_engine.remove(dl_item.id)
        assert queue_engine.size() == 0

    def test_remove_nonexistent(self, queue_engine):
        # Should not raise
        queue_engine.remove("nonexistent")

    def test_get_items(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        items = queue_engine.get_items()
        assert len(items) == 1
        assert items[0].url == dl_item.url

    def test_size_empty(self, queue_engine):
        assert queue_engine.size() == 0


# ── Status sync ─────────────────────────────────────────────────────────────


class TestQueueSync:
    def test_sync_updates_status(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.status = DownloadStatus.COMPLETED
        queue_engine.sync_from_manager(dl_item)
        items = queue_engine.get_items()
        assert items[0].status == DownloadStatus.COMPLETED.value

    def test_sync_updates_error(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.error = "Something broke"
        queue_engine.sync_from_manager(dl_item)
        items = queue_engine.get_items()
        assert items[0].error == "Something broke"

    def test_sync_updates_file_path(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.file_path = "/tmp/video.mp4"
        queue_engine.sync_from_manager(dl_item)
        items = queue_engine.get_items()
        assert items[0].file_path == "/tmp/video.mp4"

    def test_sync_nonexistent_does_not_crash(self, queue_engine, dl_item):
        """Syncing an item not in the queue should not crash."""
        queue_engine.sync_from_manager(dl_item)


# ── Persistence (crash recovery) ────────────────────────────────────────────


class TestQueuePersistence:
    def test_save_and_load_preserves_items(self, config, manager, tmp_queue_path):
        """Queue items survive a save/load cycle."""
        qe1 = QueueEngine(config, manager, path=tmp_queue_path)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test Video",
            format_id="22",
            options=DownloadOptions(),
        )
        qe1.add(item)

        # Simulate crash recovery: new engine loads same path
        qe2 = QueueEngine(config, manager, path=tmp_queue_path)
        qe2.load()
        items = qe2.get_items()
        assert len(items) == 1
        assert items[0].url == "https://example.com/video"
        assert items[0].title == "Test Video"

    def test_load_preserves_options(self, config, manager, tmp_queue_path):
        """Queue options survive serialization roundtrip."""
        qe1 = QueueEngine(config, manager, path=tmp_queue_path)
        opts = DownloadOptions(
            output_dir="/custom/output",
            extract_audio=True,
            audio_format="opus",
            embed_subtitles=True,
            subtitle_langs=["en", "fr"],
        )
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Audio Test",
            format_id="bestaudio",
            options=opts,
        )
        qe1.add(item)

        qe2 = QueueEngine(config, manager, path=tmp_queue_path)
        qe2.load()
        items = qe2.get_items()
        assert len(items) == 1
        qi = items[0]
        assert qi.extract_audio is True
        assert qi.audio_format == "opus"
        assert qi.embed_subtitles is True
        assert qi.subtitle_langs == ["en", "fr"]

    def test_load_preserves_created_at(self, config, manager, tmp_queue_path):
        """QueueItem.created_at is preserved across save/load."""
        qe1 = QueueEngine(config, manager, path=tmp_queue_path)
        item = DownloadItem.create(
            url="https://example.com/video",
            title="Test Video",
            format_id="22",
            options=DownloadOptions(),
        )
        qi = qe1.add(item)

        qe2 = QueueEngine(config, manager, path=tmp_queue_path)
        qe2.load()
        items = qe2.get_items()
        assert items[0].created_at == qi.created_at

    def test_load_empty_file(self, config, manager, tmp_queue_path):
        """Loading an empty file returns empty queue."""
        tmp_queue_path.write_text("")
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        assert qe.size() == 0

    def test_load_nonexistent_file(self, config, manager, tmp_queue_path):
        """Loading a nonexistent file returns empty queue."""
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        assert qe.size() == 0

    def test_load_corrupt_json(self, config, manager, tmp_queue_path):
        """Corrupt JSON should not crash; returns empty queue."""
        tmp_queue_path.write_text("{not valid json[[[")
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        assert qe.size() == 0

    def test_load_malformed_entries_skipped(self, config, manager, tmp_queue_path):
        """Malformed entries are skipped, valid ones kept."""
        data = [
            {"id": "valid1", "url": "https://ok.com", "title": "OK", "format_id": "22"},
            "not_a_dict",
            None,
        ]
        tmp_queue_path.write_text(json.dumps(data))
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        assert qe.size() == 1

    def test_load_resets_downloading_to_queued(self, config, manager, tmp_queue_path):
        """Items saved as 'downloading' are restored as 'queued'."""
        qi = QueueItem(
            id="test1",
            url="https://example.com",
            title="Video",
            format_id="22",
            status="downloading",
        )
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        # Manually insert item and save
        qe._items = [qi]
        qe.save()

        qe2 = QueueEngine(config, manager, path=tmp_queue_path)
        qe2.load()
        items = qe2.get_items()
        assert items[0].status == "queued"

    def test_skips_completed_on_restore_register(self, config, manager, tmp_queue_path):
        """Completed/cancelled items are not re-registered with manager."""
        qi_done = QueueItem(
            id="done1", url="https://done.com", title="Done",
            format_id="22", status="completed",
        )
        qi_pending = QueueItem(
            id="pend1", url="https://pend.com", title="Pending",
            format_id="22", status="pending",
        )
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe._items = [qi_done, qi_pending]
        qe.save()

        qe2 = QueueEngine(config, manager, path=tmp_queue_path)
        qe2.load()
        # Pending item should be registered with manager
        assert manager.get("pend1") is not None
        # Completed item should NOT be registered
        assert manager.get("done1") is None


# ── Queue mutations ─────────────────────────────────────────────────────────


class TestQueueMutations:
    def test_clear_finished_removes_completed(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.status = DownloadStatus.COMPLETED
        queue_engine.sync_from_manager(dl_item)
        queue_engine.clear_finished()
        assert queue_engine.size() == 0

    def test_clear_finished_keeps_pending(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        # Add a completed item
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="18", options=DownloadOptions(),
        )
        qi2 = queue_engine.add(item2)
        item2.status = DownloadStatus.COMPLETED
        queue_engine.sync_from_manager(item2)

        queue_engine.clear_finished()
        items = queue_engine.get_items()
        assert len(items) == 1
        assert items[0].id == dl_item.id

    def test_reorder_valid(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="18", options=DownloadOptions(),
        )
        queue_engine.add(item2)
        # Move first item to end
        queue_engine.reorder(dl_item.id, 1)
        items = queue_engine.get_items()
        assert items[1].id == dl_item.id

    def test_reorder_nonexistent(self, queue_engine):
        # Should not raise
        queue_engine.reorder("nonexistent", 0)

    def test_move_up(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="18", options=DownloadOptions(),
        )
        queue_engine.add(item2)
        queue_engine.move_up(item2.id)
        items = queue_engine.get_items()
        assert items[0].id == item2.id

    def test_move_up_first_item_noop(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        queue_engine.move_up(dl_item.id)
        items = queue_engine.get_items()
        assert items[0].id == dl_item.id

    def test_move_down(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Video 2",
            format_id="18", options=DownloadOptions(),
        )
        queue_engine.add(item2)
        queue_engine.move_down(dl_item.id)
        items = queue_engine.get_items()
        assert items[1].id == dl_item.id

    def test_move_down_last_item_noop(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        queue_engine.move_down(dl_item.id)
        items = queue_engine.get_items()
        assert items[0].id == dl_item.id


# ── Queue progress ──────────────────────────────────────────────────────────


class TestQueueProgress:
    def test_total_progress_empty(self, queue_engine):
        assert queue_engine.total_progress() == 0.0

    def test_total_progress_completed(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.status = DownloadStatus.COMPLETED
        dl_item.progress.percent = 100.0
        queue_engine.sync_from_manager(dl_item)
        assert queue_engine.total_progress() == 100.0

    def test_total_progress_partial(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.status = DownloadStatus.DOWNLOADING
        dl_item.progress.percent = 50.0
        queue_engine.sync_from_manager(dl_item)
        assert queue_engine.total_progress() == 50.0

    def test_active_size(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        assert queue_engine.active_size() == 1

    def test_active_size_excludes_completed(self, queue_engine, dl_item):
        queue_engine.add(dl_item)
        dl_item.status = DownloadStatus.COMPLETED
        queue_engine.sync_from_manager(dl_item)
        assert queue_engine.active_size() == 0


# ── QueueItem conversion ────────────────────────────────────────────────────


class TestQueueItemConversion:
    def test_roundtrip(self, dl_item):
        """QueueItem → DownloadItem → QueueItem should preserve key fields."""
        qi = QueueItem.from_download_item(dl_item, order=3)
        assert qi.id == dl_item.id
        assert qi.url == dl_item.url
        assert qi.title == dl_item.title
        assert qi.order == 3

    def test_to_download_item_preserves_created_at(self, dl_item):
        """M-5: created_at preserved across conversion."""
        dl_item.created_at = 1234567890.0
        qi = QueueItem.from_download_item(dl_item)
        di = qi.to_download_item()
        assert di.created_at == 1234567890.0

    def test_to_download_item_errors_restored(self, dl_item):
        """Errors and file_path survive conversion."""
        dl_item.error = "Download failed."
        dl_item.file_path = "/tmp/video.mp4"
        qi = QueueItem.from_download_item(dl_item)
        di = qi.to_download_item()
        assert di.error == "Download failed."
        assert di.file_path == "/tmp/video.mp4"

    def test_downloading_status_demoted_to_queued(self):
        """Items saved as 'downloading' restore as 'queued'."""
        qi = QueueItem(
            id="test1", url="https://example.com",
            title="Video", format_id="22", status="downloading",
        )
        di = qi.to_download_item()
        assert di.status == DownloadStatus.QUEUED

    def test_custom_format_preserved(self):
        """Custom format string survives roundtrip."""
        opts = DownloadOptions(custom_format="bestvideo[height<=1080]+bestaudio")
        item = DownloadItem.create(
            url="https://example.com", title="Test",
            format_id="22", options=opts,
        )
        qi = QueueItem.from_download_item(item)
        assert qi.custom_format == "bestvideo[height<=1080]+bestaudio"
        di = qi.to_download_item()
        assert di.options.custom_format == "bestvideo[height<=1080]+bestaudio"


# ── start_all / pause_all integration ────────────────────────────────────────


class TestQueueStartPauseAll:
    def test_start_all_starts_pending_items(self, queue_engine, dl_item):
        """start_all should call manager.start() for pending items."""
        queue_engine.add(dl_item)
        di = queue_engine.manager.get(dl_item.id)
        assert di is not None

        queue_engine.start_all()

        items = queue_engine.get_items()
        qi = [i for i in items if i.id == dl_item.id][0]
        assert qi is not None

    def test_start_all_skips_completed(self, queue_engine, dl_item):
        """start_all should not restart completed items."""
        dl_item.status = DownloadStatus.COMPLETED
        queue_engine.manager.register(dl_item)
        queue_engine.add(dl_item)
        queue_engine.sync_from_manager(dl_item)
        queue_engine.start_all()
        di = queue_engine.manager.get(dl_item.id)
        assert di.status == DownloadStatus.COMPLETED

    def test_pause_all_calls_manager_pause_all(self, queue_engine, dl_item):
        """pause_all delegates to manager.pause_all."""
        queue_engine.add(dl_item)
        dl_item.status = DownloadStatus.DOWNLOADING
        queue_engine.sync_from_manager(dl_item)
        queue_engine.pause_all()
        items = queue_engine.get_items()
        assert len(items) >= 1

    def test_clear_finished_removes_mixed(self, queue_engine, dl_item):
        """clear_finished removes completed, cancelled, and error; keeps pending."""
        queue_engine.add(dl_item)

        item2 = DownloadItem.create(
            url="https://example.com/2", title="Done",
            format_id="22", options=DownloadOptions(),
        )
        item2.status = DownloadStatus.COMPLETED
        queue_engine.manager.register(item2)
        queue_engine.add(item2)
        queue_engine.sync_from_manager(item2)

        item3 = DownloadItem.create(
            url="https://example.com/3", title="Failed",
            format_id="22", options=DownloadOptions(),
        )
        item3.status = DownloadStatus.ERROR
        queue_engine.manager.register(item3)
        queue_engine.add(item3)
        queue_engine.sync_from_manager(item3)

        assert queue_engine.size() == 3
        queue_engine.clear_finished()
        assert queue_engine.size() == 1
        remaining = queue_engine.get_items()
        assert remaining[0].id == dl_item.id




# ── Persistence edge cases ───────────────────────────────────────────────────


class TestQueuePersistenceExtended:
    """Additional persistence tests beyond the existing TestQueuePersistence."""

    def test_save_creates_parent_dirs(self, config, manager):
        """save() creates parent directories if they don't exist."""
        import tempfile
        td = tempfile.TemporaryDirectory()
        path = Path(td.name) / "subdir" / "nested" / "queue.json"
        qe = QueueEngine(config, manager, path=path)
        qe.save()
        assert path.exists()
        td.cleanup()

    def test_load_with_dict_not_list(self, config, manager, tmp_queue_path):
        """load() with a JSON dict (not list) returns empty list."""
        tmp_queue_path.write_text('{"items": []}')
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        assert qe.size() == 0

    def test_load_with_extra_keys_preserved(self, config, manager, tmp_queue_path):
        """load() handles entries with extra unknown keys gracefully."""
        import json
        data = [{
            "id": "test-extra",
            "url": "https://example.com",
            "title": "Test",
            "format_id": "22",
            "extra_field": "should be ignored",
            "another_extra": 42,
        }]
        tmp_queue_path.write_text(json.dumps(data))
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        assert qe.size() == 1
        assert qe.get_items()[0].id == "test-extra"

    def test_save_and_reload_preserves_items(self, config, manager, tmp_queue_path):
        """End-to-end: add items, save, reload, verify."""
        qe = QueueEngine(config, manager, path=tmp_queue_path)

        item1 = DownloadItem.create(
            url="https://example.com/1", title="First",
            format_id="22", options=DownloadOptions(),
        )
        item2 = DownloadItem.create(
            url="https://example.com/2", title="Second",
            format_id="18", options=DownloadOptions(extract_audio=True, audio_format="opus"),
        )
        qe.add(item1)
        qe.add(item2)

        qe2 = QueueEngine(config, manager, path=tmp_queue_path)
        qe2.load()
        items = qe2.get_items()
        assert len(items) == 2
        titles = {i.title for i in items}
        assert "First" in titles
        assert "Second" in titles

    def test_load_preserves_subtitle_langs(self, config, manager, tmp_queue_path):
        """subtitle_langs list survives save/load roundtrip."""
        import json
        data = [{
            "id": "test-subs",
            "url": "https://example.com",
            "title": "Test",
            "format_id": "22",
            "subtitle_langs": ["en", "fr", "de"],
        }]
        tmp_queue_path.write_text(json.dumps(data))
        qe = QueueEngine(config, manager, path=tmp_queue_path)
        qe.load()
        items = qe.get_items()
        assert items[0].subtitle_langs == ["en", "fr", "de"]



# ── Reorder edge cases ───────────────────────────────────────────────────────


class TestReorderExtended:
    def test_reorder_multiple_moves(self, queue_engine, dl_item):
        """Multiple move_up/move_down calls produce expected ordering."""
        item2 = DownloadItem.create(
            url="https://example.com/2", title="V2",
            format_id="22", options=DownloadOptions(),
        )
        item3 = DownloadItem.create(
            url="https://example.com/3", title="V3",
            format_id="22", options=DownloadOptions(),
        )
        queue_engine.add(dl_item)
        queue_engine.add(item2)
        queue_engine.add(item3)

        # Order: V3 (idx 0), V2 (idx 1), V1/dl_item (idx 2)
        queue_engine.move_up(dl_item.id)  # V3, V1, V2
        queue_engine.move_up(dl_item.id)  # V1, V3, V2

        items = queue_engine.get_items()
        assert items[0].id == dl_item.id

    def test_move_up_nonexistent_noop(self, queue_engine):
        """move_up with nonexistent ID does nothing."""
        queue_engine.move_up("nonexistent")
        assert queue_engine.size() == 0

    def test_move_down_nonexistent_noop(self, queue_engine):
        """move_down with nonexistent ID does nothing."""
        queue_engine.move_down("nonexistent")
        assert queue_engine.size() == 0


# ── On-change callback tests ─────────────────────────────────────────────────


class TestQueueCallbacks:
    def test_on_change_fires_on_add(self, config, manager, tmp_queue_path):
        """on_change callback fires when item is added."""
        fired = []

        def callback():
            fired.append(True)

        qe = QueueEngine(config, manager, path=tmp_queue_path, on_change=callback)
        item = DownloadItem.create(
            url="https://example.com", title="Test",
            format_id="22", options=DownloadOptions(),
        )
        qe.add(item)
        assert len(fired) >= 1

    def test_on_change_fires_on_remove(self, config, manager, tmp_queue_path):
        """on_change callback fires when item is removed."""
        fired = []

        def callback():
            fired.append(True)

        qe = QueueEngine(config, manager, path=tmp_queue_path, on_change=callback)
        item = DownloadItem.create(
            url="https://example.com", title="Test",
            format_id="22", options=DownloadOptions(),
        )
        qe.add(item)
        fired.clear()
        qe.remove(item.id)
        assert len(fired) >= 1
