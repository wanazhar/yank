
"""Tests for round-4 audit fixes: filesize=0, dead _active_count, status validation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from yank.engine.formats import _parse_format
from yank.engine.downloader import DownloadManager
from yank.models.history import HistoryStore, HistoryEntry, _coerce_history_status


# ── D1: _parse_format filesize=0 not confused with None ────────────────────


class TestParseFormatFilesize:
    """D1: filesize=0 uses exact value, not approximate."""

    def test_filesize_zero_preserved(self):
        fmt = _parse_format({
            "format_id": "1",
            "ext": "mp4",
            "filesize": 0,
            "filesize_approx": 5000000,
        })
        assert fmt.filesize == 0

    def test_filesize_absent_uses_approx(self):
        fmt = _parse_format({
            "format_id": "1",
            "ext": "mp4",
            "filesize_approx": 5000000,
        })
        assert fmt.filesize == 5000000

    def test_filesize_present_ignores_approx(self):
        fmt = _parse_format({
            "format_id": "1",
            "ext": "mp4",
            "filesize": 1000000,
            "filesize_approx": 5000000,
        })
        assert fmt.filesize == 1000000

    def test_both_absent_returns_none(self):
        fmt = _parse_format({
            "format_id": "1",
            "ext": "mp4",
        })
        assert fmt.filesize is None

    def test_filesize_none_uses_approx(self):
        """None is distinct from 0 — should use approx."""
        fmt = _parse_format({
            "format_id": "1",
            "ext": "mp4",
            "filesize": None,
            "filesize_approx": 5000000,
        })
        assert fmt.filesize == 5000000


# ── D2: _active_count dead field removed ───────────────────────────────────


class TestActiveCountRemoved:
    """D2: _active_count field no longer present in DownloadManager.__init__."""

    def test_active_count_field_absent(self):
        """Verify _active_count is not in __init__ anymore."""
        source = Path("src/yank/engine/downloader.py").read_text()
        # Find the __init__ method body
        in_init = False
        for line in source.splitlines():
            if "def __init__" in line:
                in_init = True
            elif in_init and line.strip() and not line.startswith(" "):
                in_init = False
            if in_init and "_active_count" in line:
                pytest.fail(f"_active_count still present in __init__: {line.strip()}")

    def test_active_count_not_used_elsewhere(self):
        """Verify _active_count is not referenced anywhere in the file."""
        source = Path("src/yank/engine/downloader.py").read_text()
        # Should only appear in the class docstring or nowhere
        lines_with_active = [
            l for l in source.splitlines()
            if "_active_count" in l and not l.strip().startswith("#")
        ]
        assert len(lines_with_active) == 0, (
            f"_active_count referenced at: {lines_with_active}"
        )


# ── D3: history status validation ─────────────────────────────────────────


class TestHistoryStatusValidation:
    """D3: loaded status values are coerced to valid literals."""

    def test_coerce_valid_success(self):
        assert _coerce_history_status("success") == "success"

    def test_coerce_valid_error(self):
        assert _coerce_history_status("error") == "error"

    def test_coerce_valid_cancelled(self):
        assert _coerce_history_status("cancelled") == "cancelled"

    def test_coerce_invalid_defaults_to_error(self):
        assert _coerce_history_status("in_progress") == "error"
        assert _coerce_history_status("pending") == "error"
        assert _coerce_history_status("") == "error"

    def test_coerce_none_defaults_to_error(self):
        assert _coerce_history_status(None) == "error"

    def test_coerce_non_string_defaults_to_error(self):
        assert _coerce_history_status(42) == "error"
        assert _coerce_history_status(True) == "error"

    def test_load_with_invalid_status_coerces(self):
        """Loading history with invalid status coerces to 'error'."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            data = [
                {"date": "2024-01-01", "title": "Test",
                 "url": "https://x.com", "format_id": "22",
                 "file_path": "/tmp/v.mp4", "status": "bad_status"},
            ]
            path.write_text(json.dumps(data))

            store = HistoryStore(path=path)
            store.load()
            entries = store.to_list()
            assert len(entries) == 1
            assert entries[0].status == "error"

    def test_load_with_valid_status_preserved(self):
        """Loading history with valid status preserves it."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            data = [
                {"date": "2024-01-01", "title": "Test",
                 "url": "https://x.com", "format_id": "22",
                 "file_path": "/tmp/v.mp4", "status": "success"},
            ]
            path.write_text(json.dumps(data))

            store = HistoryStore(path=path)
            store.load()
            entries = store.to_list()
            assert len(entries) == 1
            assert entries[0].status == "success"
