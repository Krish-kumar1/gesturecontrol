"""
video_capture.py — Dedicated camera thread.

Captures frames at the configured resolution / FPS and places them on
a thread-safe queue. Implements reconnection logic with toast notification
on disconnect.
"""

import cv2
import threading
import time
import logging
import queue
from config import settings
from notifications import notify

logger = logging.getLogger(__name__)

class VideoCaptureThread(threading.Thread):
    """
    Daemon thread: grabs frames from a webcam and puts them in `frame_queue`.
    On camera disconnect it notifies the user and blocks until reconnected.
    """

    RECONNECT_INTERVAL = 3.0   # seconds between reconnect attempts

    def __init__(self, frame_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(name="VideoCaptureThread", daemon=True)
        self.frame_queue = frame_queue
        self.stop_event  = stop_event
        self._cap: cv2.VideoCapture | None = None

    # ── Public ───────────────────────────────────────────────────────────────

    @property
    def is_healthy(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ── Internals ────────────────────────────────────────────────────────────

    def _open_camera(self) -> bool:
        idx = settings["camera_index"]
        cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
        if not cap.isOpened():
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  settings["frame_width"])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings["frame_height"])
        cap.set(cv2.CAP_PROP_FPS,          settings["target_fps"])
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # minimise latency
        self._cap = cap
        logger.info("Camera %s opened.", idx)
        return True

    def _release(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    def run(self):
        frame_interval = 1.0 / settings["target_fps"]

        while not self.stop_event.is_set():
            # ── Attempt connection ───────────────────────────────────────────
            if not self._open_camera():
                notify("Gesture Control",
                       "Camera not found. Retrying…",
                       urgency="normal")
                self.stop_event.wait(self.RECONNECT_INTERVAL)
                continue

            # ── Capture loop ─────────────────────────────────────────────────
            t_next = time.monotonic()
            while not self.stop_event.is_set():
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("Camera read failed — disconnected?")
                    notify("Gesture Control",
                           "Camera disconnected. Waiting for reconnection…",
                           urgency="critical")
                    self._release()
                    break   # back to outer reconnect loop

                # Rate-limit to target FPS
                now = time.monotonic()
                if now >= t_next:
                    # Flip horizontally for natural mirror mapping
                    frame = cv2.flip(frame, 1)
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        pass   # drop frame; downstream is behind
                    t_next = now + frame_interval

                time.sleep(0.001)   # yield CPU

        self._release()
        logger.info("VideoCaptureThread exiting.")