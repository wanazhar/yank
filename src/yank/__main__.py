"""Entry point: ``python -m yank`` or ``yank`` CLI."""

from __future__ import annotations


def main() -> None:
    """Launch the yank CLI (TUI or ``yank connect``)."""
    from yank.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
