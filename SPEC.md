# yank — yt-dlp TUI wrapper

## What it is

A terminal user interface (TUI) that wraps yt-dlp. The user never types yt-dlp arguments directly. Everything is interactive — paste URL, pick format, choose options, hit download. Also manages yt-dlp itself (install, update).

## Target user

Someone who uses yt-dlp occasionally but can't remember the flags. Wants something they can just run without Googling.

## Tech stack

- **Language:** Python 3.11+
- **TUI framework:** Textual (the rich TUI library)
- **yt-dlp:** Used as a Python library (not subprocess) — import yt-dlp directly for format extraction and downloading
- **Config:** TOML file at ~/.config/yank/config.toml
- **History:** JSON file at ~/.local/share/yank/history.json
- **Package management:** pipx or uv tool for install

## Features (build ALL, no stubs)

### 1. URL input screen
- Text input for pasting URLs
- Detect platform (YouTube, TikTok, Twitter/X, Instagram, Vimeo, etc.) from the URL
- Allow pasting multiple URLs for batch queue

### 2. Format selection screen
- Fetch available formats from yt-dlp
- Show them in a tabular list with columns: ID, Extension, Resolution, Filesize, Codec, Note
- Allow arrow key navigation and spacebar to select
- Pre-select best quality by default
- Indicators: video+audio combined vs separate, audio-only, subtitles available
- Side panel with video metadata (title, duration, uploader, upload date)

### 3. Options screen
- Output directory (default: ~/Downloads, but configurable)
- Filename template (default: `%(title)s.%(ext)s`)
- Download thumbnail (yes/no)
- Embed metadata (yes/no)
- Embed subtitles (yes/no — only shown if available)
- Subtitle language picker (only shown if subs available)
- Download format override (allow typing custom yt-dlp format string for power users)
- Extract audio only toggle → switches to best audio format
- Audio format picker (mp3, m4a, opus, flac) when audio only is toggled

### 4. Download screen
- Real-time progress bar for each active download
- Show: ETA, speed, percentage, file being written
- Support concurrent downloads (default: 1, configurable up to 5)
- Pause/cancel individual downloads
- Error display per download (clear error messages, not yt-dlp stack traces)

### 5. Queue management
- Tab/panel showing all queued downloads
- Reorder, remove items
- Batch start / pause all
- Show total progress across queue

### 6. History tab
- Chronological list of past downloads
- Columns: Date, Title, URL, Format, File path, Status (success/error)
- Click to re-download or copy info
- Search/filter by title or URL

### 7. Configuration screen
- Default download directory (browser-style directory picker or typed path)
- Default format preference: best / best video+audio / audio only
- Max concurrent downloads (1-5)
- Default filename template
- Default subtitle language
- yt-dlp update check interval (always/ask/never)

### 8. yt-dlp management
- On first run: check if yt-dlp is installed, if not auto-install it via pip
- On startup: check for yt-dlp updates if last check > 24h, show notification if update available
- Config screen shows current yt-dlp version with "Check for updates" button
- yt-dlp is managed as a pip dependency — update via `pip install -U yt-dlp` or equivalent

## Behavior & user experience

- **Keyboard-first:** Tab/arrow navigation, Enter to confirm, Escape to go back, Ctrl+C to quit
- **But also mouse-friendly** (Textual supports mouse natively)
- Startup screen shows URL input immediately — no splash screen, no delay
- Status bar at bottom showing: current yt-dlp version, queue size, disk space
- Error messages are human readable — never yt-dlp tracebacks
- All states handled: no internet, invalid URL, format fetch fails, download fails, disk full

## Non-goals

- Not a YouTube browser (no search, no trending)
- Not a media player
- Not a GUI
- No cloud sync, no accounts, no telemetry

## Directory structure

```
work/yank/
├── README.md
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── __main__.py          # entry point: `python -m yank` or `yank` CLI
│   ├── app.py               # Textual app class
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── url_input.py     # URL input screen
│   │   ├── format_select.py # Format selection screen
│   │   ├── options.py       # Options/config screen
│   │   ├── download.py      # Download progress screen
│   │   ├── queue.py         # Queue management screen
│   │   ├── history.py       # History screen
│   │   └── settings.py      # Settings screen
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── formats.py       # Format fetching and parsing
│   │   ├── downloader.py    # Download manager
│   │   ├── queue.py         # Queue engine
│   │   └── updater.py       # yt-dlp management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── history.py       # History storage
│   │   └── config.py        # Config loading/saving
│   └── widgets/
│       ├── __init__.py
│       ├── progress.py      # Custom progress bar widget
│       ├── format_table.py  # Format list table widget
│       └── status_bar.py     # Bottom status bar widget
└── tests/
    ├── __init__.py
    └── test_formats.py
```

## Implementation notes

- Use `yt_dlp.extractor_info()` for format data (not subprocess)
- Use `yt_dlp.YoutubeDL` with progress hooks for download callbacks
- Parse format data into structured dataclasses
- Queue is in-memory + persisted to JSON for crash recovery
- Config uses `tomllib` (stdlib in Python 3.11+)
- Textual screens are composable — use `Screen` subclasses, push/pop navigation
- Style: minimal, dark theme, readable at any font size