"""Read local owner controls shared by scheduled Python workers."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / ".cache" / "control-room" / "settings.json"


def read_control_settings():
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def enabled_map(settings, name, defaults):
    saved = settings.get(name)
    if not isinstance(saved, dict):
        saved = {}
    return {
        key: saved.get(key) if isinstance(saved.get(key), bool) else default
        for key, default in defaults.items()
    }
