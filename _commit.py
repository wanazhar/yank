#!/usr/bin/env python3
"""Git commit helper v2 — stage specific file groups per commit."""
import subprocess, sys

def run(cmd):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/ubuntu/work/yank")
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr, file=sys.stderr)
    return r.returncode == 0

def commit(title, body, files):
    run(["git", "reset", "HEAD"])
    for f in files: run(["git", "add", f])
    msg = title + "\n\n" + "\n".join(body)
    run(["git", "commit", "-m", msg])

print("=== SOFT RESET ===")
run(["git", "reset", "--soft", "HEAD~1"])
run(["git", "reset", "HEAD"])

print("=== COMMIT 1: Architecture ===")
commit("refactor: fix type annotations, extract shared CSS, create services container", [
    "- Add typed attributes for config, history, manager, queue, ytdlp to YankApp",
    "- Replace # type: ignore[attr-defined] with proper typed _app properties",
    "- Extract shared CSS patterns from 7 screens into src/yank/styles.py",
    "- Create AppServices dataclass for cleaner dependency injection",
    "- Fix version to use importlib.metadata",
    "- Break circular imports with lazy screen registry",
    "- Extract _coerce_* helpers to src/yank/_safe_types.py",
    "- Consolidate path constants to src/yank/paths.py",
    "- Extract magic numbers to src/yank/constants.py",
    "- Replace hand-rolled version parser with packaging.version",
    "- Remove unused Static imports from 4 screen files",
], ["src/yank/app.py","src/yank/__init__.py","src/yank/_version.py","src/yank/services.py",
    "src/yank/styles.py","src/yank/_safe_types.py","src/yank/paths.py","src/yank/constants.py",
    "src/yank/engine/updater.py","src/yank/engine/queue.py","src/yank/models/history.py",
    "src/yank/screens/__init__.py","src/yank/screens/url_input.py","src/yank/screens/format_select.py",
    "src/yank/screens/options.py","src/yank/screens/download.py","src/yank/screens/queue.py",
    "src/yank/screens/history.py","src/yank/screens/settings.py","src/yank/widgets/format_table.py",
    "src/yank/widgets/status_bar.py","src/yank/widgets/progress.py"])

print("\n=== COMMIT 2: Security ===")
commit("fix: replace bare excepts with logging, add config validation", [
    "- Create src/yank/logging.py with file+console logger",
    "- Replace bare except:pass with _logger.debug(exc_info=True)",
    "- Add download_dir existence/writable validation in AppConfig",
    "- Improve error path sanitization",
], ["src/yank/logging.py","src/yank/models/config.py",
    "src/yank/engine/formats.py","src/yank/engine/downloader.py"])

print("\n=== COMMIT 3: Testing ===")
commit("test: add comprehensive tests for engine and models", [
    "- Add tests/test_downloader.py: mocked YoutubeDL, pause/cancel/hooks",
    "- Add tests/test_queue.py: add/remove/reorder/persistence",
    "- Add tests/test_updater.py: version check/install/update flows",
    "- Expand tests/test_config.py: TOML round-trip, validation",
    "- Add tests/test_history.py: 1000-entry cap, search, concurrent access",
], ["tests/test_downloader.py","tests/test_queue.py","tests/test_updater.py",
    "tests/test_config.py","tests/test_history.py"])

print("\n=== COMMIT 4: UX ===")
commit("feat: add clipboard detection, post-download actions, desktop notifications", [
    "- Auto-detect clipboard URL on URL input screen mount",
    "- Add Ctrl+V binding for clipboard paste",
    "- Add Open file, Open folder, Copy path buttons in History",
    "- Add column sorting with sort indicators in History DataTable",
    "- Create src/yank/notify.py for cross-platform desktop notifications",
    "- Add proxy URL field to Settings and DownloadOptions",
    "- Add enable_notifications and proxy fields to AppConfig",
], ["src/yank/notify.py"])

print("\n=== COMMIT 5: DevOps ===")
commit("chore: add mypy, ruff, CI, packaging config", [
    "- Add [tool.mypy] to pyproject.toml with check_untyped_defs",
    "- Add [tool.ruff] lint + format config with isort, bugbear, pyupgrade",
    "- Add [tool.pytest.ini_options] with coverage config",
    "- Add pytest-cov to dev dependencies",
    "- Create .github/workflows/ci.yml (Python 3.11/3.12/3.13 matrix)",
    "- Create MANIFEST.in for source distribution",
    "- Create .gitignore with standard Python patterns",
], ["pyproject.toml",".github/workflows/ci.yml","MANIFEST.in",".gitignore","LICENSE"])

print("\n=== COMMIT 6: Remaining ===")
run(["git","add","-A"])
run(["git","commit","-m","chore: add build helpers and misc files\n\n- Add Makefile for common tasks\n- Add remaining test files"])

print("\n=== FINAL LOG ===")
run(["git","log","--oneline","-10"])
print("\nDone!")


