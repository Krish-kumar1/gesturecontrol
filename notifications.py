"""
notifications.py — OS toast / desktop notifications.

Uses plyer for cross-platform (Windows/macOS/Linux) desktop notifications.
Falls back to a simple print if plyer is unavailable.
No network calls are made.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from plyer import notification as _plyer_notify
    _PLYER_AVAILABLE = True
except ImportError:
    _PLYER_AVAILABLE = False
    logger.warning("plyer not installed — toast notifications disabled.")


def notify(title: str, message: str,
           urgency: str = "normal", timeout: int = 5) -> None:
    """
    Show a desktop notification.
    urgency: 'low' | 'normal' | 'critical'  (advisory; support varies by OS)
    """
    logger.info("[NOTIFY] %s: %s", title, message)
    if not _PLYER_AVAILABLE:
        print(f"[{urgency.upper()}] {title}: {message}")
        return
    try:
        _plyer_notify.notify(
            title=title,
            message=message,
            app_name="GestureControl",
            timeout=timeout,
        )
    except Exception as exc:
        logger.debug("Toast notification failed: %s", exc)