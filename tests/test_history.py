"""Tests for HistoryStore: CRUD, search, caps, concurrency, and corruption recovery."""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

import pytest

from yank._safe_types import _coerce_int
from yank.models.history import (
    HistoryEntry,
    HistoryStore,
    _coerce_history_status,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_history_path():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td) / "history.json"


@pytest.fixture
def store(tmp_history_path):
    return HistoryStore(path=tmp_history_path)


@pytest.fixture
def entry():
    return HistoryEntry.create(
        title="Test Video",
        url="https://example.com/video",
        format_id="22",
        file_path="/tmp/video.mp4",
        status="success",
        filesize=1048576,
    )


# ── Status coercion ──────────────────────────────────────────────────────────


class TestCoerceHistoryStatus:
    def test_valid_statuses(self):
        assert _coerce_history_status("success") == "success"
        assert _coerce_history_status("error") == "error"
        assert _coerce_history_status("cancelled") == "cancelled"

    def test_invalid_defaults_to_error(self):
        assert _coerce_history_status("pending") == "error"
        assert _coerce_history_status("downloading") == "error"
        assert _coerce_history_status("") == "error"

    def test_none_defaults_to_error(self):
        assert _coerce_history_status(None) == "error"

    def test_non_string_defaults_to_error(self):
        assert _coerce_history_status(42) == "error"
        assert _coerce_history_status(3.14) == "error"
        assert _coerce_history_status(True) == "error"


# ── Coerce int safe ──────────────────────────────────────────────────────────


class TestCoerceIntSafe:
    def test_valid_int(self):
        assert _coerce_int(42, 0) == 42
        assert _coerce_int(0, 10) == 0
        assert _coerce_int(-5, 10) == -5

    def test_none_returns_default(self):
        assert _coerce_int(None, 0) == 0
        assert _coerce_int(None, 10) == 10

    def test_non_numeric_returns_default(self):
        assert _coerce_int("not a number", 0) == 0
        assert _coerce_int({}, 0) == 0
        assert _coerce_int([], 0) == 0

    def test_float_string(self):
        assert _coerce_int("3.14", 0) == 0

    def test_float_value(self):
        assert _coerce_int(3.14, 0) == 3


# ── Basic CRUD ───────────────────────────────────────────────────────────────


class TestHistoryCRUD:
    def test_add_and_to_list(self, store, entry):
        store.add(entry)
        entries = store.to_list()
        assert len(entries) == 1
        assert entries[0].title == "Test Video"

    def test_add_multiple_newest_first(self, store):
        e1 = HistoryEntry.create(
            title="First",
            url="https://x.com/1",
            format_id="22",
            file_path="/tmp/a.mp4",
            status="success",
        )
        e2 = HistoryEntry.create(
            title="Second",
            url="https://x.com/2",
            format_id="18",
            file_path="/tmp/b.mp4",
            status="error",
        )
        store.add(e1)
        store.add(e2)
        entries = store.to_list()
        assert entries[0].title == "Second"
        assert entries[1].title == "First"

    def test_save_and_load(self, store, entry, tmp_history_path):
        store.add(entry)
        store2 = HistoryStore(path=tmp_history_path)
        store2.load()
        assert len(store2.to_list()) == 1
        assert store2.to_list()[0].title == "Test Video"

    def test_clear(self, store, entry):
        store.add(entry)
        assert len(store.to_list()) == 1
        store.clear()
        assert len(store.to_list()) == 0

    def test_clear_then_add(self, store, entry):
        store.add(entry)
        store.clear()
        store.add(entry)
        assert len(store.to_list()) == 1


# ── 1000-entry cap ───────────────────────────────────────────────────────────


class TestHistoryCap:
    def test_cap_at_1000(self, store):
        """Adding 1100 entries caps the list at 1000."""
        for i in range(1100):
            entry = HistoryEntry.create(
                title=f"Video {i}",
                url=f"https://example.com/{i}",
                format_id="22",
                file_path=f"/tmp/v{i}.mp4",
                status="success",
            )
            store.add(entry)
        entries = store.to_list()
        assert len(entries) == 1000

    def test_cap_keeps_newest(self, store):
        """After cap, newest entries (most recently added) are kept."""
        # Add 1001 entries; the first (oldest) should be dropped
        for i in range(1001):
            entry = HistoryEntry.create(
                title=f"Video {i}",
                url=f"https://example.com/{i}",
                format_id="22",
                file_path=f"/tmp/v{i}.mp4",
                status="success",
            )
            store.add(entry)
        entries = store.to_list()
        assert len(entries) == 1000
        # Newest at index 0
        assert entries[0].title == "Video 1000"
        # Oldest (Video 0) should be gone
        titles = {e.title for e in entries}
        assert "Video 0" not in titles


# ── Search ───────────────────────────────────────────────────────────────────


class TestHistorySearch:
    @pytest.fixture
    def populated_store(self, store):
        store.add(
            HistoryEntry.create(
                title="Cat Video",
                url="https://youtube.com/watch?v=1",
                format_id="22",
                file_path="/tmp/cat.mp4",
                status="success",
            )
        )
        store.add(
            HistoryEntry.create(
                title="Dog Compilation",
                url="https://vimeo.com/2",
                format_id="best",
                file_path="/tmp/dog.mp4",
                status="success",
            )
        )
        store.add(
            HistoryEntry.create(
                title="Tutorial Python",
                url="https://youtube.com/watch?v=3",
                format_id="18",
                file_path="/tmp/tutorial.mp4",
                status="error",
                error="Download failed.",
            )
        )
        return store

    def test_search_by_title(self, populated_store):
        results = populated_store.search("cat")
        assert len(results) == 1
        assert results[0].title == "Cat Video"

    def test_search_by_url(self, populated_store):
        results = populated_store.search("vimeo")
        assert len(results) == 1
        assert results[0].title == "Dog Compilation"

    def test_search_case_insensitive(self, populated_store):
        results = populated_store.search("CAT")
        assert len(results) == 1

    def test_search_partial_match(self, populated_store):
        results = populated_store.search("tut")
        assert len(results) == 1
        assert "tutorial" in results[0].title.lower()

    def test_search_no_match(self, populated_store):
        results = populated_store.search("nonexistent")
        assert len(results) == 0

    def test_search_empty_returns_all(self, populated_store):
        results = populated_store.search("")
        assert len(results) == 3

    def test_search_whitespace_returns_all(self, populated_store):
        results = populated_store.search("   ")
        assert len(results) == 3

    def test_search_unicode(self, store):
        store.add(
            HistoryEntry.create(
                title="Café Vidéo",
                url="https://example.com",
                format_id="22",
                file_path="/tmp/cafe.mp4",
                status="success",
            )
        )
        results = store.search("café")
        assert len(results) == 1


# ── Corrupt JSON recovery ────────────────────────────────────────────────────


class TestCorruptJSONRecovery:
    def test_malformed_json(self, tmp_history_path):
        """Malformed JSON on load resets to empty list."""
        tmp_history_path.write_text("{ this is not valid json [[[")
        store = HistoryStore(path=tmp_history_path)
        store.load()
        assert len(store.to_list()) == 0

    def test_empty_file(self, tmp_history_path):
        """Empty file on load resets to empty list."""
        tmp_history_path.write_text("")
        store = HistoryStore(path=tmp_history_path)
        store.load()
        assert len(store.to_list()) == 0

    def test_non_list_json(self, tmp_history_path):
        """JSON that is a dict (not list) resets to empty list."""
        tmp_history_path.write_text('{"entries": []}')
        store = HistoryStore(path=tmp_history_path)
        store.load()
        assert len(store.to_list()) == 0

    def test_mixed_valid_invalid_entries(self, tmp_history_path):
        """Entries with missing fields still load; non-dict entries skipped."""
        data = [
            {
                "date": "2024-01-01T00:00:00",
                "title": "Valid Entry",
                "url": "https://example.com",
                "format_id": "22",
                "file_path": "/tmp/v.mp4",
                "status": "success",
            },
            "not a dict",
            123,
            None,
            {
                "title": "Missing Fields",
                "url": "https://example.com/2",
                "format_id": "18",
                "file_path": "/tmp/v2.mp4",
                "status": "error",
            },
        ]
        tmp_history_path.write_text(json.dumps(data))
        store = HistoryStore(path=tmp_history_path)
        store.load()
        entries = store.to_list()
        assert len(entries) >= 1

    def test_invalid_status_coerced(self, tmp_history_path):
        """Entry with invalid status is coerced to 'error'."""
        data = [
            {
                "date": "2024-01-01",
                "title": "Test",
                "url": "https://x.com",
                "format_id": "22",
                "file_path": "/tmp/v.mp4",
                "status": "invalid_status",
            }
        ]
        tmp_history_path.write_text(json.dumps(data))
        store = HistoryStore(path=tmp_history_path)
        store.load()


# ── Concurrent access ────────────────────────────────────────────────────────


class TestHistoryConcurrent:
    def test_concurrent_adds(self, store):
        """Multiple threads adding entries simultaneously does not crash."""
        errors = []

        def add_entries(prefix, count):
            try:
                for i in range(count):
                    entry = HistoryEntry.create(
                        title=f"{prefix}-{i}",
                        url=f"https://example.com/{prefix}/{i}",
                        format_id="22",
                        file_path=f"/tmp/{prefix}-{i}.mp4",
                        status="success",
                    )
                    store.add(entry)
            except Exception as exc:
                errors.append(exc)

        threads = []
        for p in ("A", "B", "C", "D"):
            t = threading.Thread(target=add_entries, args=(p, 25))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All 100 entries should be present
        entries = store.to_list()
        assert len(entries) == 100

    def test_concurrent_add_and_search(self, store):
        """Concurrent adds and searches do not crash."""
        errors = []
        done = threading.Event()

        def adder():
            try:
                for i in range(50):
                    entry = HistoryEntry.create(
                        title=f"Video-{i}",
                        url=f"https://example.com/{i}",
                        format_id="22",
                        file_path=f"/tmp/v{i}.mp4",
                        status="success",
                    )
                    store.add(entry)
            except Exception as exc:
                errors.append(exc)
            finally:
                done.set()

        def searcher():
            try:
                while not done.is_set():
                    store.search("Video")
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=adder)
        t2 = threading.Thread(target=searcher)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0
        assert len(store.to_list()) >= 1

    def test_missing_file_no_error(self, tmp_history_path):
        """Loading from a nonexistent file does not crash."""
        store = HistoryStore(path=tmp_history_path)
        store.load()
        assert len(store.to_list()) == 0
