"""
gesture_recognizer.py — Gesture detection from MediaPipe landmarks.

Gestures implemented
────────────────────
  MOVE   — Index fingertip drives cursor (landmark 8).
  CLICK  — Pinch: thumb tip (4) ↔ index tip (8) distance < threshold.
  SCROLL — Two-finger slide: index (8) + middle (12) move vertically
           while ring (16) + pinky (20) are folded.

All coordinates are normalised [0, 1].
"""

from dataclasses import dataclass, field
from enum import Enum, auto
import time
import math


class GestureType(Enum):
    NONE   = auto()
    MOVE   = auto()
    CLICK  = auto()
    SCROLL = auto()


@dataclass
class GestureResult:
    gesture:    GestureType = GestureType.NONE
    x:          float = 0.0          # Normalised cursor X  (MOVE / CLICK)
    y:          float = 0.0          # Normalised cursor Y  (MOVE / CLICK)
    scroll_dy:  float = 0.0          # Scroll delta (SCROLL; positive = up)
    confidence: float = 1.0


# MediaPipe hand landmark indices (21 landmarks total)
_TIP   = {4: "THUMB", 8: "INDEX", 12: "MIDDLE", 16: "RING", 20: "PINKY"}
THUMB_TIP  = 4
INDEX_TIP  = 8
MIDDLE_TIP = 12
RING_TIP   = 16
PINKY_TIP  = 20
# MCP (knuckle) joints for fold detection
INDEX_MCP  = 5
MIDDLE_MCP = 9
RING_MCP   = 13
PINKY_MCP  = 17


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _is_folded(tip, mcp, wrist) -> bool:
    """True when fingertip is closer to wrist than the MCP knuckle."""
    return _dist(tip, wrist) < _dist(mcp, wrist) * 1.1


class GestureRecognizer:
    def __init__(self, pinch_threshold: float = 0.045,
                 scroll_deadzone: float = 0.02):
        self.pinch_threshold  = pinch_threshold
        self.scroll_deadzone  = scroll_deadzone

        self._prev_scroll_y: float | None = None
        self._pinch_down:    bool  = False
        self._click_sent:    bool  = False
        self._last_click_ts: float = 0.0
        self._click_cooldown = 0.35    # seconds between clicks

    def process(self, landmarks) -> GestureResult:
        """
        landmarks: list[NormalizedLandmark] from MediaPipe (21 items).
        Returns a GestureResult describing the dominant gesture.
        """
        if not landmarks or len(landmarks) < 21:
            return GestureResult()

        lm = landmarks
        wrist = lm[0]

        # ── Pinch detection ──────────────────────────────────────────────────
        pinch_dist = _dist(lm[THUMB_TIP], lm[INDEX_TIP])
        is_pinching = pinch_dist < self.pinch_threshold

        if is_pinching:
            now = time.monotonic()
            if not self._pinch_down and (now - self._last_click_ts) > self._click_cooldown:
                self._pinch_down  = True
                self._last_click_ts = now
                cx = (lm[THUMB_TIP].x + lm[INDEX_TIP].x) / 2
                cy = (lm[THUMB_TIP].y + lm[INDEX_TIP].y) / 2
                return GestureResult(GestureType.CLICK, cx, cy, confidence=1.0)
        else:
            self._pinch_down = False

        # ── Two-finger scroll detection ──────────────────────────────────────
        ring_folded  = _is_folded(lm[RING_TIP],  lm[RING_MCP],  wrist)
        pinky_folded = _is_folded(lm[PINKY_TIP], lm[PINKY_MCP], wrist)

        if ring_folded and pinky_folded:
            mid_y = (lm[INDEX_TIP].y + lm[MIDDLE_TIP].y) / 2
            mid_x = (lm[INDEX_TIP].x + lm[MIDDLE_TIP].x) / 2

            if self._prev_scroll_y is not None:
                dy = self._prev_scroll_y - mid_y   # positive = fingers moved up = scroll up
                if abs(dy) > self.scroll_deadzone:
                    self._prev_scroll_y = mid_y
                    return GestureResult(GestureType.SCROLL,
                                         mid_x, mid_y, scroll_dy=dy)
            self._prev_scroll_y = mid_y
            return GestureResult(GestureType.MOVE, mid_x, mid_y)
        else:
            self._prev_scroll_y = None

        # ── Index-tip move (default) ─────────────────────────────────────────
        return GestureResult(GestureType.MOVE,
                              lm[INDEX_TIP].x, lm[INDEX_TIP].y)