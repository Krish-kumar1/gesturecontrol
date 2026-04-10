"""
input_executor.py — PyAutoGUI input execution thread.

Consumes GestureResult objects and translates them into OS-level
mouse/scroll actions. The MovingAverageFilter is applied here so the
cursor never jitters.

No network code of any kind is present in this module.
"""

import threading
import time
import logging
import queue

import pyautogui

from config import settings
from filters import MovingAverageFilter
from gesture_recognizer import GestureResult, GestureType

logger = logging.getLogger(__name__)

pyautogui.FAILSAFE   = False   # We implement our own kill-switch
pyautogui.PAUSE      = 0.0     # Remove built-in delay; we control timing


class InputExecutorThread(threading.Thread):
    """
    Daemon thread that reads GestureResult objects and drives the OS cursor.
    """

    def __init__(self, gesture_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(name="InputExecutorThread", daemon=True)
        self.gesture_queue = gesture_queue
        self.stop_event    = stop_event

        self._filter = MovingAverageFilter(window=settings["smoothing_window"])
        self._screen_w, self._screen_h = pyautogui.size()

    @property
    def is_healthy(self) -> bool:
        return self.is_alive()

    def run(self):
        sensitivity = settings["move_sensitivity"]
        scroll_sens = settings["scroll_sensitivity"]

        while not self.stop_event.is_set():
            try:
                gesture: GestureResult = self.gesture_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if gesture.gesture == GestureType.NONE:
                self._filter.reset()
                continue

            if gesture.gesture == GestureType.MOVE:
                sx, sy = self._norm_to_screen(gesture.x, gesture.y, sensitivity)
                fx, fy = self._filter.update(sx, sy)
                pyautogui.moveTo(int(fx), int(fy))

            elif gesture.gesture == GestureType.CLICK:
                sx, sy = self._norm_to_screen(gesture.x, gesture.y, sensitivity)
                fx, fy = self._filter.update(sx, sy)
                pyautogui.click(int(fx), int(fy))
                logger.debug("Click at (%d, %d)", fx, fy)

            elif gesture.gesture == GestureType.SCROLL:
                clicks = int(gesture.scroll_dy * scroll_sens)
                if clicks != 0:
                    pyautogui.scroll(clicks)
                    logger.debug("Scroll %+d", clicks)

        logger.info("InputExecutorThread exiting.")

    def _norm_to_screen(self, nx: float, ny: float,
                         sensitivity: float) -> tuple[float, float]:
        """
        Map normalised [0,1] landmark coords to screen pixel coords.
        Applies sensitivity scaling around the screen centre.
        """
        cx = self._screen_w / 2
        cy = self._screen_h / 2
        sx = cx + (nx - 0.5) * self._screen_w * sensitivity
        sy = cy + (ny - 0.5) * self._screen_h * sensitivity
        # Clamp to screen bounds
        sx = max(0.0, min(float(self._screen_w - 1), sx))
        sy = max(0.0, min(float(self._screen_h - 1), sy))
        return sx, sy