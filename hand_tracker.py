"""
hand_tracker.py — MediaPipe Hands processing thread.

Consumes raw frames from frame_queue, runs hand landmark detection,
and puts GestureResult objects into gesture_queue.
Implements Sleep Mode: when no hand is detected for `sleep_mode_timeout`
seconds the thread polls at a much lower rate to save CPU.
"""

import threading
import time
import logging
import queue

import cv2
import mediapipe as mp

from config import settings
from gesture_recognizer import GestureRecognizer, GestureResult, GestureType

logger = logging.getLogger(__name__)

_mp_hands   = mp.solutions.hands
_mp_drawing = mp.solutions.drawing_utils


class HandTrackerThread(threading.Thread):
    """
    Daemon thread that converts video frames → GestureResults.
    """

    def __init__(self,
                 frame_queue:   queue.Queue,
                 gesture_queue: queue.Queue,
                 stop_event:    threading.Event):
        super().__init__(name="HandTrackerThread", daemon=True)
        self.frame_queue   = frame_queue
        self.gesture_queue = gesture_queue
        self.stop_event    = stop_event

        self._recognizer = GestureRecognizer(
            pinch_threshold = settings["pinch_threshold"],
            scroll_deadzone = settings["scroll_deadzone"],
        )
        self._last_hand_ts: float = time.monotonic()
        self._sleeping:     bool  = False

    # ── Public ───────────────────────────────────────────────────────────────

    @property
    def is_healthy(self) -> bool:
        """Watchdog uses this to confirm the thread is alive."""
        return self.is_alive()

    # ── Internals ────────────────────────────────────────────────────────────

    def run(self):
        sleep_timeout  = settings["sleep_mode_timeout"]
        sleep_interval = settings["sleep_poll_interval"]
        show_debug     = settings["show_debug_window"]

        with _mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6,
        ) as hands:

            while not self.stop_event.is_set():
                # ── Sleep mode ───────────────────────────────────────────────
                if self._sleeping:
                    time.sleep(sleep_interval)
                    # Drain and check for a frame to wake up
                    try:
                        frame = self.frame_queue.get_nowait()
                    except queue.Empty:
                        continue
                else:
                    try:
                        frame = self.frame_queue.get(timeout=0.05)
                    except queue.Empty:
                        continue

                # ── Process frame ────────────────────────────────────────────
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False
                result = hands.process(rgb)
                rgb.flags.writeable = True

                if result.multi_hand_landmarks:
                    self._last_hand_ts = time.monotonic()
                    self._sleeping     = False
                    landmarks = result.multi_hand_landmarks[0].landmark
                    gesture   = self._recognizer.process(landmarks)

                    if show_debug:
                        self._draw_debug(frame, result)

                else:
                    # No hand detected
                    if (time.monotonic() - self._last_hand_ts) > sleep_timeout:
                        if not self._sleeping:
                            logger.debug("No hand detected — entering sleep mode.")
                        self._sleeping = True
                    gesture = GestureResult(GestureType.NONE)

                try:
                    self.gesture_queue.put_nowait(gesture)
                except queue.Full:
                    pass

        logger.info("HandTrackerThread exiting.")

    @staticmethod
    def _draw_debug(frame, result):
        for hl in result.multi_hand_landmarks:
            _mp_drawing.draw_landmarks(
                frame, hl, _mp_hands.HAND_CONNECTIONS)
        cv2.imshow("GestureControl — Debug", frame)
        cv2.waitKey(1)