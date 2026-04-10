"""
config.py — Encrypted settings management.
Fernet symmetric encryption protects settings.enc at rest.
The key is derived deterministically from a machine-specific secret.
"""

import json, uuid, hashlib, logging, base64
from pathlib import Path
from typing import Any
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

BASE_DIR    = Path(__file__).parent
CONFIG_DIR  = BASE_DIR / "data"
CONFIG_PATH = CONFIG_DIR / "settings.enc"
KEY_PATH    = CONFIG_DIR / "key.bin"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

DEFAULTS: dict[str, Any] = {
    "camera_index":        0,
    "frame_width":         640,
    "frame_height":        480,
    "target_fps":          80,
    "smoothing_window":    25,      # Moving-average window size
    "move_sensitivity":    2.5,
    "pinch_threshold":     0.045,  # Normalised 0-1 distance
    "scroll_sensitivity":  3000,
    "scroll_deadzone":     0.02,
    "sleep_mode_timeout":  3.0,    # Seconds without hand → sleep
    "sleep_poll_interval": 0.5,
    "kill_hotkey":         "<ctrl>+<shift>+q",
    "show_debug_window":   False,
    "log_level":           "INFO",
}

def _machine_secret() -> bytes:
    return hashlib.sha256(f"gesture-ctrl-{uuid.getnode()}".encode()).digest()

def _load_or_create_key() -> Fernet:
    if KEY_PATH.exists():
        try:
            return Fernet(KEY_PATH.read_bytes())
        except Exception:
            logger.warning("Key corrupt — regenerating.")
    key = base64.urlsafe_b64encode(_machine_secret())
    KEY_PATH.write_bytes(key)
    KEY_PATH.chmod(0o600)
    return Fernet(key)

_fernet = _load_or_create_key()

class Settings:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self.load()

    def load(self):
        if not CONFIG_PATH.exists():
            self._data = dict(DEFAULTS); self.save(); return
        try:
            plain = _fernet.decrypt(CONFIG_PATH.read_bytes())
            self._data = {**DEFAULTS, **json.loads(plain)}
        except (InvalidToken, json.JSONDecodeError) as e:
            logger.error("Settings decrypt failed (%s) — using defaults.", e)
            self._data = dict(DEFAULTS)

    def save(self):
        CONFIG_PATH.write_bytes(_fernet.encrypt(json.dumps(self._data, indent=2).encode()))
        CONFIG_PATH.chmod(0o600)

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._data.get(key, fallback)

    def set(self, key: str, value: Any):
        self._data[key] = value; self.save()

    def __getitem__(self, k): return self._data[k]
    def __setitem__(self, k, v): self.set(k, v)

settings = Settings()