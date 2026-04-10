"""
watchdog.py — Thread-health watchdog.

Monitors every registered thread. If a thread is found dead, it logs the
event and fires an optional callback (e.g., to restart the thread or
alert the user via a toast notification).
"""

import threading
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)

_SENTINEL = object()


class Watchdog(threading.Thread):
    """
    Polls registered threads every `interval` seconds.
    On detecting a dead thread it calls the registered callback.
    """

    def __init__(self, interval: float = 2.0):
        super().__init__(name="WatchdogThread", daemon=True)
        self._interval  = interval
        self._targets:   dict[str, threading.Thread]   = {}
        self._callbacks: dict[str, Callable[[str], None]] = {}
        self._lock       = threading.Lock()
        self._stop_event = threading.Event()

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, name: str, thread: threading.Thread,
                 on_dead: Callable[[str], None] | None = None):
        with self._lock:
            self._targets[name]   = thread
            self._callbacks[name] = on_dead or (lambda n: None)
        logger.debug("Watchdog: registered '%s'.", name)

    def unregister(self, name: str):
        with self._lock:
            self._targets.pop(name, None)
            self._callbacks.pop(name, None)

    def stop(self):
        self._stop_event.set()

    # ── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        while not self._stop_event.is_set():
            time.sleep(self._interval)
            with self._lock:
                snapshot = dict(self._targets)
                cbs      = dict(self._callbacks)

            for name, thread in snapshot.items():
                if not thread.is_alive():
                    logger.error("Watchdog: thread '%s' is DEAD.", name)
                    try:
                        cbs[name](name)
                    except Exception as exc:
                        logger.exception("Watchdog callback error: %s", exc)

        logger.info("WatchdogThread exiting.")