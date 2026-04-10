"""
tray.py — pystray system-tray icon.

Provides a minimal tray icon with:
  • Status indicator (active / paused)
  • Toggle pause / resume
  • Open settings (stub — wire to a GUI if desired)
  • Quit (triggers the global stop_event)
"""

import threading
import logging
from io import BytesIO

try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

logger = logging.getLogger(__name__)


def _make_icon(active: bool = True) -> "Image.Image":
    """Draw a simple coloured circle as the tray icon."""
    size   = 64
    colour = (0, 200, 80) if active else (200, 80, 0)
    img    = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)
    margin = 6
    draw.ellipse([margin, margin, size - margin, size - margin], fill=colour)
    return img


class TrayManager:
    """Manages the system-tray icon lifecycle in a background thread."""

    def __init__(self, stop_event: threading.Event,
                 pause_event: threading.Event):
        self._stop_event  = stop_event
        self._pause_event = pause_event
        self._icon: "pystray.Icon | None" = None

    def start(self):
        if not _TRAY_AVAILABLE:
            logger.warning("pystray / Pillow not available — no tray icon.")
            return
        t = threading.Thread(target=self._run, name="TrayThread", daemon=True)
        t.start()

    def _run(self):
        icon = pystray.Icon(
            "GestureControl",
            icon=_make_icon(active=True),
            title="Gesture Control",
            menu=pystray.Menu(
                pystray.MenuItem("Toggle Pause", self._toggle_pause),
                pystray.MenuItem("Quit",         self._quit),
            ),
        )
        self._icon = icon
        icon.run()   # blocks until icon.stop() is called

    def _toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self._set_icon(active=True)
            logger.info("Resumed.")
        else:
            self._pause_event.set()
            self._set_icon(active=False)
            logger.info("Paused.")

    def _quit(self):
        logger.info("Quit requested from tray.")
        self._stop_event.set()
        if self._icon:
            self._icon.stop()

    def _set_icon(self, active: bool):
        if self._icon:
            self._icon.icon = _make_icon(active)