"""Entry point: ``python -m yank`` or ``yank`` CLI."""

from __future__ import annotations


def main() -> None:
    """Launch the yank Textual application."""
    from yank.app import YankApp

    app = YankApp()
    app.run()


if __name__ == "__main__":
    main()
