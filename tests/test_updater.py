
"""Tests for yt-dlp updater version comparison and helpers."""

from __future__ import annotations

from yank.engine.updater import _version_is_newer


class TestVersionComparison:
    """Test _version_is_newer with real yt-dlp version formats."""

    def test_simple_newer(self):
        assert _version_is_newer("2024.1.0", "2023.12.31") is True

    def test_simple_older(self):
        assert _version_is_newer("2023.1.0", "2024.1.0") is False

    def test_same_version(self):
        assert _version_is_newer("2024.1.0", "2024.1.0") is False

    def test_minor_bump(self):
        assert _version_is_newer("2024.2.0", "2024.1.0") is True

    def test_patch_bump(self):
        assert _version_is_newer("2024.1.1", "2024.1.0") is True

    def test_nightly_newer(self):
        """Nightly versions like 2024.01.01.232536 should compare correctly."""
        assert _version_is_newer("2024.01.02", "2024.01.01.232536") is True

    def test_nightly_older(self):
        assert _version_is_newer("2024.01.01", "2024.01.01.232536") is False

    def test_post_release(self):
        """Post-release suffixes are treated as older than base (text < int)."""
        assert _version_is_newer("2024.1.0.post1", "2024.1.0") is False

    def test_prerelease_is_older(self):
        """Pre-release markers are treated as older than release."""
        assert _version_is_newer("2024.1.0", "2024.1.0a1") is True

    def test_different_length_padded(self):
        """Different-length version tuples compare correctly (padded)."""
        assert _version_is_newer("2024.1.0.1", "2024.1.0") is True

    def test_leading_zeros(self):
        """Leading zeros in version segments."""
        assert _version_is_newer("2024.01.10", "2024.1.9") is True

    def test_handles_complex_suffixes(self):
        """Dashes converted to dots for chunking."""
        # yt-dlp uses dash in some version schemes
        assert _version_is_newer("2024.1.0", "2024.1.0-beta1") is True

    def test_ragged_versions(self):
        """Ragged version strings with mixed numbers/text."""
        assert _version_is_newer("2024.12.25", "2024.6.1") is True
        assert _version_is_newer("2024.6.1", "2024.12.25") is False

    def test_fallback_on_parse_error(self):
        """If parsing fails, fall back to string inequality."""
        # This shouldn't raise
        result = _version_is_newer("weird-version", "other-version")
        assert isinstance(result, bool)


class TestVersionComparisonEdgeCases:
    def test_single_segment(self):
        assert _version_is_newer("2", "1") is True
        assert _version_is_newer("1", "2") is False

    def test_major_version_jump(self):
        assert _version_is_newer("2025.1.0", "2024.12.31") is True

    def test_equal_after_padding(self):
        """2024.1 == 2024.1.0 after padding."""
        assert _version_is_newer("2024.1", "2024.1.0") is False

    def test_text_vs_number_priority(self):
        """Numeric segments are greater than text segments."""
        assert _version_is_newer("2024.1", "2024.a") is True

    def test_multiple_dash_segments(self):
        """Versions with multiple dashes handled."""
        assert _version_is_newer("2024.1.0", "2024.1.0-alpha-2") is True

    def test_post_suffix_specific(self):
        assert _version_is_newer("2024.1.0.post2", "2024.1.0.post1") is True
