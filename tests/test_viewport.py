"""Viewport helpers for Termius / Herdr canvas sizes."""

from __future__ import annotations

from yank.viewport import (
    HERDR_COLS,
    HERDR_ROWS,
    TERMius_COLS,
    TERMius_ROWS,
    content_body_rows,
    fit_height_slack,
    is_herdr_canvas,
    is_phone_canvas,
    phone_button_labels,
)


def test_phone_canvas_matches_termius_and_herdr_stty():
    assert is_phone_canvas(TERMius_COLS, TERMius_ROWS)
    assert is_phone_canvas(HERDR_COLS, HERDR_ROWS)
    assert not is_phone_canvas(80, 40)


def test_body_rows_for_measured_sizes():
    assert content_body_rows(TERMius_ROWS) == 28
    assert content_body_rows(HERDR_ROWS) == 26


def test_phone_button_labels_are_short():
    labels = phone_button_labels(batch_mode=False)
    assert len(labels["btn-batch"]) <= 6
    assert all(len(v) <= 12 for v in labels.values())


async def _fit_check(width: int, height: int, *, herdr: bool) -> tuple[int, int, int, bool]:
    import os

    from yank.app import YankApp

    app = YankApp()
    prev = os.environ.get("HERDR_ENV")
    if herdr:
        os.environ["HERDR_ENV"] = "1"
    else:
        os.environ.pop("HERDR_ENV", None)
    try:
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            screen = pilot.app.screen
            body = screen.query_one("#url-body")
            box = screen.query_one("#url-container")
            slack = fit_height_slack(herdr=herdr)
            from yank.i18n import LocalizedButton as Button

            btn = screen.query_one("#btn-continue", Button)
            label_text = str(btn.label) if btn.label else ""
            return (
                body.size.height,
                box.size.height,
                btn.size.height,
                box.size.height <= body.size.height - slack
                and bool(label_text)
                and "Continue" in btn.render().plain,
            )
    finally:
        if prev is None:
            os.environ.pop("HERDR_ENV", None)
        else:
            os.environ["HERDR_ENV"] = prev


def test_url_input_fits_termius_and_herdr_stty():
    import asyncio

    body, box, btn_h, ok = asyncio.run(
        _fit_check(TERMius_COLS, TERMius_ROWS, herdr=False)
    )
    assert ok, f"termius: box={box} body={body} btn_h={btn_h}"
    body, box, btn_h, ok = asyncio.run(_fit_check(HERDR_COLS, HERDR_ROWS, herdr=True))
    assert ok, f"herdr: box={box} body={body} btn_h={btn_h}"


def test_herdr_canvas_detection():
    assert is_herdr_canvas(HERDR_COLS, HERDR_ROWS, in_herdr=False)
    assert is_herdr_canvas(80, 40, in_herdr=True)
