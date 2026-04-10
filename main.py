"""
main.py — Application entry point and orchestrator.

Thread map
──────────
  VideoCaptureThread  →  frame_queue  →  HandTrackerThread
  HandTrackerThread   →  gesture_queue → InputExecutorThread
  WatchdogThread      monitors all three
  TrayThread          system-tray icon
  pynput.GlobalHotKeys  kill switch (runs in its own OS thread)
"""

import logging
import queue
import signal
import sys
import threading
import time

from config    import settings
from video_capture   import VideoCaptureThread
from hand_tracker    import HandTrackerThread
from input_executor  import InputExecutorThread
from watchdog        import Watchdog
from tray            import TrayManager
from notifications   import notify

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings["log_level"], logging.INFO),
    format="%(asctime)s [%(threadName)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Shared synchronisation primitives ────────────────────────────────────────
stop_event  = threading.Event()   # Set → all threads shut down
pause_event = threading.Event()   # Set → InputExecutorThread drops gestures

FRAME_QUEUE_MAXSIZE   = 4   # Small; drop stale frames
GESTURE_QUEUE_MAXSIZE = 8

frame_queue   = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
gesture_queue = queue.Queue(maxsize=GESTURE_QUEUE_MAXSIZE)


# ── Kill switch (global hotkey) ───────────────────────────────────────────────

def _setup_kill_switch():
    try:
        from pynput import keyboard

        hotkey_str = settings["kill_hotkey"]   # e.g. "<ctrl>+<shift>+q"

        def _on_activate():
            logger.warning("Kill switch activated (%s).", hotkey_str)
            notify("Gesture Control", "Kill switch activated — shutting down.")
            stop_event.set()

        # pynput.keyboard.GlobalHotKeys runs its own daemon thread
        hk = keyboard.GlobalHotKeys({hotkey_str: _on_activate})
        hk.daemon = True
        hk.start()
        logger.info("Kill switch armed: %s", hotkey_str)
    except Exception as exc:
        logger.error("Could not arm kill switch: %s", exc)


# ── Thread factories ──────────────────────────────────────────────────────────

def _on_thread_dead(name: str):
    notify("Gesture Control",
           f"Thread '{name}' died unexpectedly. Check logs.",
           urgency="critical")


def build_threads():
    capture  = VideoCaptureThread(frame_queue,   stop_event)
    tracker  = HandTrackerThread(frame_queue,    gesture_queue, stop_event)
    executor = InputExecutorThread(gesture_queue, stop_event)
    return capture, tracker, executor


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    logger.info("Gesture Control starting up.")
    notify("Gesture Control", "Application started.")

    # Kill switch
    _setup_kill_switch()

    # System-tray icon
    tray = TrayManager(stop_event=stop_event, pause_event=pause_event)
    tray.start()

    # Worker threads
    capture, tracker, executor = build_threads()
    threads = [capture, tracker, executor]

    # Watchdog
    watchdog = Watchdog(interval=2.0)
    watchdog.register("VideoCapture",  capture,  _on_thread_dead)
    watchdog.register("HandTracker",   tracker,  _on_thread_dead)
    watchdog.register("InputExecutor", executor, _on_thread_dead)

    for t in threads:
        t.start()
    watchdog.start()

    logger.info("All threads running. Press %s to quit.",
                settings["kill_hotkey"])

    # Block main thread; handle SIGINT (Ctrl-C in terminal)
    def _sigint(sig, frame):
        logger.info("SIGINT received — shutting down.")
        stop_event.set()

    signal.signal(signal.SIGINT, _sigint)

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    finally:
        logger.info("Shutdown in progress…")
        stop_event.set()
        watchdog.stop()
        for t in threads:
            t.join(timeout=5.0)
        logger.info("Gesture Control stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()