"""Tests for format parsing, platform detection, and helpers."""

from __future__ import annotations

import pytest

from yank.engine.formats import (
    FormatInfo,
    VideoMeta,
    detect_platform,
    format_selector_for,
    is_valid_url,
    pick_best_format,
    _humanize_ytdlp_error,
    _parse_format,
    _sort_key,
)


class TestDetectPlatform:
    def test_youtube(self):
        assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "YouTube"
        assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "YouTube"

    def test_tiktok(self):
        assert detect_platform("https://www.tiktok.com/@user/video/123") == "TikTok"

    def test_twitter(self):
        assert detect_platform("https://twitter.com/user/status/123") == "Twitter/X"
        assert detect_platform("https://x.com/user/status/123") == "Twitter/X"

    def test_instagram(self):
        assert detect_platform("https://www.instagram.com/p/abc/") == "Instagram"

    def test_vimeo(self):
        assert detect_platform("https://vimeo.com/12345") == "Vimeo"

    def test_unknown(self):
        assert detect_platform("https://example.com/video") == "Example"
        assert detect_platform("") == "Unknown"


class TestIsValidUrl:
    def test_valid(self):
        assert is_valid_url("https://youtube.com/watch?v=1")
        assert is_valid_url("http://example.com/a")

    def test_invalid(self):
        assert not is_valid_url("")
        assert not is_valid_url("not a url")
        assert not is_valid_url("ftp://files.example.com/x")
        assert not is_valid_url("youtube.com/watch")  # no scheme


class TestParseFormat:
    def test_combined(self):
        raw = {
            "format_id": "22",
            "ext": "mp4",
            "height": 720,
            "width": 1280,
            "vcodec": "avc1.64001F",
            "acodec": "mp4a.40.2",
            "filesize": 10485760,
            "format_note": "720p",
        }
        fmt = _parse_format(raw)
        assert fmt.format_id == "22"
        assert fmt.is_combined
        assert not fmt.is_audio_only
        assert fmt.ext == "mp4"
        assert "1280x720" in fmt.resolution or "720" in fmt.resolution
        assert fmt.filesize == 10485760

    def test_audio_only(self):
        raw = {
            "format_id": "140",
            "ext": "m4a",
            "vcodec": "none",
            "acodec": "mp4a.40.2",
            "abr": 128,
        }
        fmt = _parse_format(raw)
        assert fmt.is_audio_only
        assert not fmt.is_combined
        assert "audio" in fmt.resolution.lower() or fmt.resolution == "audio only"

    def test_video_only(self):
        raw = {
            "format_id": "137",
            "ext": "mp4",
            "vcodec": "avc1",
            "acodec": "none",
            "height": 1080,
            "width": 1920,
        }
        fmt = _parse_format(raw)
        assert fmt.is_video_only


class TestPickBest:
    def _sample_formats(self) -> list[FormatInfo]:
        return [
            FormatInfo(
                format_id="140",
                ext="m4a",
                resolution="audio only",
                filesize=3_000_000,
                vcodec="none",
                acodec="mp4a",
                note="",
                abr=128,
                is_audio_only=True,
            ),
            FormatInfo(
                format_id="137",
                ext="mp4",
                resolution="1080p",
                filesize=50_000_000,
                vcodec="avc1",
                acodec="none",
                note="",
                is_video_only=True,
            ),
            FormatInfo(
                format_id="22",
                ext="mp4",
                resolution="720p",
                filesize=20_000_000,
                vcodec="avc1",
                acodec="mp4a",
                note="",
                is_combined=True,
            ),
            FormatInfo(
                format_id="18",
                ext="mp4",
                resolution="360p",
                filesize=5_000_000,
                vcodec="avc1",
                acodec="mp4a",
                note="",
                is_combined=True,
            ),
        ]

    def test_best_prefers_combined(self):
        best = pick_best_format(self._sample_formats(), "best")
        assert best is not None
        assert best.is_combined
        assert "720" in best.resolution

    def test_audio_only(self):
        best = pick_best_format(self._sample_formats(), "audio_only")
        assert best is not None
        assert best.is_audio_only

    def test_video_audio_pref(self):
        best = pick_best_format(self._sample_formats(), "best_video_audio")
        assert best is not None
        assert best.is_video_only or best.is_combined

    def test_empty(self):
        assert pick_best_format([]) is None


class TestFormatSelector:
    def test_combined(self):
        fmt = FormatInfo(
            format_id="22",
            ext="mp4",
            resolution="720p",
            filesize=1,
            vcodec="avc1",
            acodec="mp4a",
            note="",
            is_combined=True,
        )
        assert format_selector_for(fmt) == "22"

    def test_video_only_merges_audio(self):
        fmt = FormatInfo(
            format_id="137",
            ext="mp4",
            resolution="1080p",
            filesize=1,
            vcodec="avc1",
            acodec="none",
            note="",
            is_video_only=True,
        )
        sel = format_selector_for(fmt)
        assert "137" in sel
        assert "bestaudio" in sel

    def test_custom_override(self):
        fmt = FormatInfo(
            format_id="22",
            ext="mp4",
            resolution="720p",
            filesize=1,
            vcodec="avc1",
            acodec="mp4a",
            note="",
            is_combined=True,
        )
        assert format_selector_for(fmt, custom="best") == "best"


class TestHumanizeError:
    def test_404(self):
        msg = _humanize_ytdlp_error("ERROR: HTTP Error 404: Not Found")
        assert "404" in msg or "not found" in msg.lower()

    def test_timeout(self):
        msg = _humanize_ytdlp_error("URLError: timed out")
        assert "timed out" in msg.lower() or "timeout" in msg.lower()

    def test_private(self):
        msg = _humanize_ytdlp_error("ERROR: Private video. Sign in to verify")
        assert "private" in msg.lower() or "login" in msg.lower()


class TestVideoMeta:
    def test_duration_display(self):
        m = VideoMeta(url="https://x.com", duration=3661)
        assert m.duration_display == "1:01:01"
        m2 = VideoMeta(url="https://x.com", duration=125)
        assert m2.duration_display == "2:05"

    def test_upload_date(self):
        m = VideoMeta(url="https://x.com", upload_date="20240704")
        assert m.upload_date_display == "2024-07-04"

    def test_subtitles(self):
        m = VideoMeta(
            url="https://x.com",
            subtitles={"en": [{}], "es": [{}]},
            automatic_captions={"fr": [{}]},
        )
        assert m.has_subtitles
        assert "en" in m.available_subtitle_langs
        assert "fr" in m.available_subtitle_langs


class TestConfig:
    def test_defaults(self):
        from yank.models.config import AppConfig

        cfg = AppConfig().ensure_valid()
        assert cfg.max_concurrent == 1
        assert "%(title)s" in cfg.filename_template

    def test_clamp_concurrent(self):
        from yank.models.config import AppConfig

        cfg = AppConfig(max_concurrent=99).ensure_valid()
        assert cfg.max_concurrent == 5
        cfg2 = AppConfig(max_concurrent=0).ensure_valid()
        assert cfg2.max_concurrent == 1


class TestHistory:
    def test_create_and_search(self, tmp_path):
        from yank.models.history import HistoryEntry, HistoryStore

        store = HistoryStore(path=tmp_path / "history.json")
        store.add(
            HistoryEntry.create(
                title="Demo Video",
                url="https://youtube.com/watch?v=1",
                format_id="22",
                file_path="/tmp/demo.mp4",
                status="success",
            )
        )
        store.add(
            HistoryEntry.create(
                title="Other",
                url="https://vimeo.com/2",
                format_id="best",
                file_path="/tmp/other.mp4",
                status="error",
                error="fail",
            )
        )
        assert len(store.to_list()) == 2
        found = store.search("demo")
        assert len(found) == 1
        assert found[0].title == "Demo Video"
        found2 = store.search("vimeo")
        assert len(found2) == 1

        # reload
        store2 = HistoryStore(path=tmp_path / "history.json")
        store2.load()
        assert len(store2.to_list()) == 2
