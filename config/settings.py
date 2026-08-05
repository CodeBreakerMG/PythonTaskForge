# App settings — stored outside the project so .app builds work cleanly.

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "TaskForge"


def app_support_dir() -> Path:
    """Stable per-user config location (macOS Application Support, else ~/.taskforge)."""
    if os.name == "posix" and (Path.home() / "Library" / "Application Support").exists():
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / f".{APP_NAME.lower()}"


def settings_path() -> Path:
    return app_support_dir() / "settings.json"


def default_db_path() -> Path:
    """
    Prefer an existing project DB for backward compatibility.
    Otherwise use Application Support (better for packaged apps).
    """
    legacy = PROJECT_ROOT / "database" / "taskforge.db"
    if legacy.exists():
        return legacy.resolve()
    return (app_support_dir() / "taskforge.db").resolve()


@dataclass
class AppSettings:
    db_path: str

    @classmethod
    def defaults(cls) -> "AppSettings":
        return cls(db_path=str(default_db_path()))


def load_settings() -> AppSettings:
    path = settings_path()
    if not path.exists():
        return AppSettings.defaults()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings.defaults()

    db_path = raw.get("db_path") or str(default_db_path())
    return AppSettings(db_path=str(Path(db_path).expanduser()))


def save_settings(settings: AppSettings) -> Path:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(settings)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
