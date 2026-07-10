
"""Tests for round-8 audit: UI/UX fixes — history search, queue timer, redundant code."""

from __future__ import annotations

from pathlib import Path


# ── U11: History refresh no longer calls store.load() ────────────────────────


class TestHistoryRefreshNoDiskLoad:
    """U11: refresh_table should not call store.load() on every keystroke."""

    def test_refresh_table_does_not_load_from_disk(self):
        """Verify store.load() is no longer in refresh_table."""
        source = Path("src/yank/screens/history.py").read_text()
        in_refresh = False
        for line in source.splitlines():
            if "def refresh_table" in line:
                in_refresh = True
            elif in_refresh and line.strip().startswith("def "):
                in_refresh = False
            elif in_refresh and "store.load()" in line:
                pytest.fail(
                    f"store.load() still present in refresh_table: {line.strip()}"
                )


# ── U22: Queue timer pauses when screen not active ──────────────────────────


class TestQueueTimerGuarded:
    """U22: Queue refresh timer checks is_current before refreshing."""

    def test_tick_refresh_method_exists(self):
        """Verify _tick_refresh method exists and checks screen visibility."""
        source = Path("src/yank/screens/queue.py").read_text()
        assert "def _tick_refresh" in source, (
            "_tick_refresh method missing from QueueScreen"
        )
        assert "self.app.screen is self" in source, (
            "_tick_refresh should check self.app.screen is self"
        )

    def test_timer_uses_tick_refresh(self):
        """The timer should call _tick_refresh, not refresh_table directly."""
        source = Path("src/yank/screens/queue.py").read_text()
        assert "set_interval(0.5, self._tick_refresh)" in source, (
            "Timer should use _tick_refresh instead of refresh_table directly"
        )


# ── U21: Redundant on_mount code noted ──────────────────────────────────────


class TestOptionsScreenRedundancy:
    """U21: The compose CSS classes already handle subtitle visibility."""

    def test_subtitle_widgets_hidden_via_css(self):
        """Subtitle widgets use CSS classes for hiding, not just on_mount."""
        source = Path("src/yank/screens/options.py").read_text()
        # The Checkbox and Select use classes="" or classes="hidden"
        assert 'classes="" if has_subs else "hidden"' in source, (
            "Subtitle widgets should use CSS classes for hiding"
        )
