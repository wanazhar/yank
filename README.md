# yank ⬇️

**A beautiful TUI wrapper for yt-dlp.** Paste a URL, pick a format, download. No flags to remember.

```
                      __
   __  ______ _____  / /__
  / / / / __ `/ __ \/ //_/
 / /_/ / /_/ / / / / ,<
 \__, /\__,_/_/ /_/_/|_|
/____/

         yt-dlp TUI wrapper

    Paste a video URL · or multiple URLs (one per line) for batch

  ┌────────────────────────────────────────────────────────────────┐
  │ https://…                                                      │
  └────────────────────────────────────────────────────────────────┘

  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐
  │   Continue   │  │   Batch mode   │  │    Clear     │
  └──────────────┘  └────────────────┘  └──────────────┘

  Queue [F2]    History [F3]    Settings [F4]
```

## Features

- **URL input** — paste one or multiple URLs, auto-detects platform (YouTube, TikTok, Twitter/X, Instagram, Vimeo, etc.)
- **Format browser** — interactive table of available formats with resolution, codec, filesize
- **Download manager** — real-time progress bars with speed, ETA, per-download controls
- **Queue system** — batch multiple downloads, reorder, pause, cancel
- **History** — every download logged with title, URL, format, and status
- **Settings** — default download directory, format preferences, concurrent downloads, audio extraction
- **yt-dlp management** — auto-installs and updates yt-dlp, no manual setup
- **Beautiful dark theme** — purple/cyan accent palette with tasteful terminal styling
- **Keyboard + mouse** — navigate with arrow keys or click

## Installation

### Quick install (recommended)

```bash
pipx install yank-tui
```

Or from source:

```bash
git clone https://github.com/wanazhar/yank.git
cd yank
uv venv
uv sync
```

## Usage

```bash
yank
```

Or from source:

```bash
cd yank && .venv/bin/python -m yank
```

### Workflow

1. **Paste a URL** — the app opens to a clean input screen. Paste a video URL (YouTube, TikTok, etc.)
2. **Choose format** — browse available formats in a sortable table. Best quality is pre-selected
3. **Configure options** — set output directory, filename template, subtitles, thumbnail
4. **Download** — watch real-time progress with speed and ETA
5. **Done** — file saved, logged to history

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Esc` | Back / Quit |
| `F2` | Queue view |
| `F3` | History |
| `F4` | Settings |
| `Ctrl+Q` | Quit |
| `Ctrl+P` | Palette |
| `↑↓` | Navigate |
| `Space` | Select |
| `Enter` | Confirm |

## Configuration

Config stored at `~/.config/yank/config.toml`:

```toml
download_dir = "/home/user/Downloads"
format_preference = "best"
max_concurrent = 2
filename_template = "%(title)s.%(ext)s"
subtitle_lang = "en"
```

## How it works

yank wraps **yt-dlp** as a Python library (not subprocess). All format extraction, downloading, and metadata handling goes through `yt_dlp.YoutubeDL` with progress hooks. The TUI is built with **Textual** — a modern Python terminal UI framework.

The app is fully local. No cloud, no accounts, no telemetry. Your downloads and history never leave your machine.

## Requirements

- Python 3.11+
- A terminal that supports 24-bit color (most modern terminals do)
- `ffmpeg` (optional — needed for some format merges and audio extraction)

## License

MIT
