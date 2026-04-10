"""
filters.py — Signal processing utilities.
MovingAverageFilter smooths noisy landmark coordinates to prevent
mouse jitter caused by MediaPipe micro-oscillations.
"""

from collections import deque
import numpy as np

class MovingAverageFilter:
    """
    Keeps a rolling window of (x, y) samples and returns their mean.
    Window size is configurable at runtime.
    """

    def __init__(self, window: int = 7):
        self._window = window
        self._buf_x: deque[float] = deque(maxlen=window)
        self._buf_y: deque[float] = deque(maxlen=window)

    def resize(self, window: int):
        """Change window size without losing existing samples."""
        self._window = window
        self._buf_x = deque(self._buf_x, maxlen=window)
        self._buf_y = deque(self._buf_y, maxlen=window)

    def update(self, x: float, y: float) -> tuple[float, float]:
        self._buf_x.append(x)
        self._buf_y.append(y)
        return float(np.mean(self._buf_x)), float(np.mean(self._buf_y))

    def reset(self):
        self._buf_x.clear()
        self._buf_y.clear()