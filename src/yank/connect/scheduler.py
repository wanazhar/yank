"""Background scheduler hooks (parity with TUI ``release_scheduled``)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yank.connect.runtime import ConnectRuntime


def start_queue_scheduler(runtime: ConnectRuntime, *, interval_s: float = 10.0) -> threading.Event:
    stop = threading.Event()

    def _loop() -> None:
        while not stop.wait(interval_s):
            try:
                released = runtime.queue.release_scheduled()
                if released:
                    runtime.manager.start_queued()
            except Exception:
                pass

    thread = threading.Thread(target=_loop, name="yank-connect-scheduler", daemon=True)
    thread.start()
    runtime._scheduler_stop = stop  # type: ignore[attr-defined]
    return stop


def stop_queue_scheduler(runtime: ConnectRuntime) -> None:
    stop = getattr(runtime, "_scheduler_stop", None)
    if stop is not None:
        stop.set()
