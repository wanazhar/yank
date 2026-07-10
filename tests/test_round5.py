
"""Tests for round-5 audit: QueueEngine.load() safe coercion, format table edge cases."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from yank.engine.downloader import DownloadManager, DownloadOptions
from yank.engine.queue import (
    QueueEngine,
    _coerce_float,
    _coerce_int,
)


@pytest.fixture
def config():
    return type("C", (), {"download_dir": "/tmp", "max_concurrent": 1})()


@pytest.fixture
def manager(config):
    return DownloadManager(config)


# ── E2: Safe coercion prevents entire-entry skip ────────────────────────────


class TestSafeCoercionLoad:
    """E2: Bad created_at/order values don't skip the entire entry."""

    def test_bad_created_at_string_does_not_skip_entry(self, config, manager):
        """A non-numeric created_at should fall back to current time, not skip."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [{
                "id": "test-bad-ts",
                "url": "https://example.com",
                "title": "Test",
                "format_id": "22",
                "created_at": "yesterday",
            }]
            path.write_text(json.dumps(data))
            qe = QueueEngine(config, manager, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 1, "Entry should not be skipped"
            assert items[0].id == "test-bad-ts"
            assert items[0].created_at > 1000000000  # fallback to now

    def test_bad_order_string_does_not_skip_entry(self, config, manager):
        """A non-numeric order should fall back to index, not skip."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [{
                "id": "test-bad-order",
                "url": "https://example.com",
                "title": "Test",
                "format_id": "22",
                "order": "first",
            }]
            path.write_text(json.dumps(data))
            qe = QueueEngine(config, manager, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 1, "Entry should not be skipped"
            assert items[0].id == "test-bad-order"
            assert items[0].order == 0  # fallback to index i

    def test_bad_created_at_null_uses_now(self, config, manager):
        """null created_at falls back to current time."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [{
                "id": "test-null-ts",
                "url": "https://example.com",
                "title": "Test",
                "format_id": "22",
                "created_at": None,
            }]
            path.write_text(json.dumps(data))
            qe = QueueEngine(config, manager, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 1
            assert items[0].created_at > 1000000000

    def test_mixed_valid_and_invalid_entries(self, config, manager):
        """Valid entries still load even if adjacent entries have bad fields."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "queue.json"
            data = [
                {
                    "id": "good1",
                    "url": "https://example.com/1",
                    "title": "Good 1",
                    "format_id": "22",
                },
                {
                    "id": "good2",
                    "url": "https://example.com/2",
                    "title": "Good 2",
                    "format_id": "22",
                    "created_at": "bad_string",
                    "order": "also_bad",
                },
            ]
            path.write_text(json.dumps(data))
            qe = QueueEngine(config, manager, path=path)
            qe.load()
            items = qe.get_items()
            assert len(items) == 2, "Both entries should load"


# ── Helper coercion tests ───────────────────────────────────────────────────


class TestCoerceFloat:
    def test_valid_float(self):
        assert _coerce_float(3.14, 0.0) == 3.14

    def test_valid_int(self):
        assert _coerce_float(42, 0.0) == 42.0

    def test_none_returns_default(self):
        assert _coerce_float(None, 99.0) == 99.0

    def test_string_returns_default(self):
        assert _coerce_float("abc", 99.0) == 99.0

    def test_zero_preserved(self):
        assert _coerce_float(0, 99.0) == 0.0


class TestCoerceInt:
    def test_valid_int(self):
        assert _coerce_int(42, 0) == 42

    def test_valid_float_truncated(self):
        assert _coerce_int(3.14, 0) == 3

    def test_none_returns_default(self):
        assert _coerce_int(None, 7) == 7

    def test_string_returns_default(self):
        assert _coerce_int("abc", 7) == 7

    def test_zero_preserved(self):
        assert _coerce_int(0, 7) == 0


# ── E2b: HistoryStore.load safe filesize coercion ──────────────────────────


class TestHistoryFilesizeCoercion:
    """E2b: Bad filesize values in history don't skip entries."""

    def test_bad_filesize_string_does_not_skip(self):
        """Non-numeric filesize falls back to 0, entry preserved."""
        with tempfile.TemporaryDirectory() as td:
            from pathlib import Path
            path = Path(td) / "history.json"
            data = [{
                "date": "2024-01-01",
                "title": "Test",
                "url": "https://x.com",
                "format_id": "22",
                "file_path": "/tmp/v.mp4",
                "status": "success",
                "filesize": "unknown",
            }]
            path.write_text(json.dumps(data))
            from yank.models.history import HistoryStore
            store = HistoryStore(path=path)
            store.load()
            entries = store.to_list()
            assert len(entries) == 1, "Entry should not be skipped"
            assert entries[0].filesize == 0

    def test_valid_filesize_preserved(self):
        """Valid filesize is preserved."""
        with tempfile.TemporaryDirectory() as td:
            from pathlib import Path
            path = Path(td) / "history.json"
            data = [{
                "date": "2024-01-01",
                "title": "Test",
                "url": "https://x.com",
                "format_id": "22",
                "file_path": "/tmp/v.mp4",
                "status": "success",
                "filesize": 12345678,
            }]
            path.write_text(json.dumps(data))
            from yank.models.history import HistoryStore
            store = HistoryStore(path=path)
            store.load()
            entries = store.to_list()
            assert entries[0].filesize == 12345678

    def test_null_filesize_defaults_to_zero(self):
        """null filesize defaults to 0."""
        with tempfile.TemporaryDirectory() as td:
            from pathlib import Path
            path = Path(td) / "history.json"
            data = [{
                "date": "2024-01-01",
                "title": "Test",
                "url": "https://x.com",
                "format_id": "22",
                "file_path": "/tmp/v.mp4",
                "status": "success",
                "filesize": None,
            }]
            path.write_text(json.dumps(data))
            from yank.models.history import HistoryStore
            store = HistoryStore(path=path)
            store.load()
            entries = store.to_list()
            assert entries[0].filesize == 0


# ── F3: query_one not called directly from worker-thread callbacks ──────────


class TestQueryOneThreadSafety:
    """F3: call_from_thread uses lambdas, not direct query_one evaluation."""

    def test_url_input_uses_lambda_not_direct_query(self):
        """Verify _fetch_and_proceed uses lambda wrappers for query_one."""
        source = Path("src/yank/screens/url_input.py").read_text()
        # The old pattern: call_from_thread(\n            self.query_one
        # Should now be: call_from_thread(\n            lambda:
        bad = "call_from_thread(\n            self.query_one"
        assert bad not in source, (
            "Direct query_one found in call_from_thread — should use lambda"
        )

    def test_settings_uses_lambda_not_direct_query(self):
        """Verify settings worker methods use lambda wrappers."""
        source = Path("src/yank/screens/settings.py").read_text()
        bad = "call_from_thread(\n            self.query_one"
        assert bad not in source, (
            "Direct query_one found in call_from_thread in settings.py"
        )
