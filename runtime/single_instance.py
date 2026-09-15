# Ensure only one TaskForge GUI instance runs at a time.

from __future__ import annotations

import os
from pathlib import Path

from config.settings import app_support_dir

LOCK_FILE = app_support_dir() / "instance.lock"


def _lock_pid() -> int | None:
    if not LOCK_FILE.exists():
        return None
    try:
        return int(LOCK_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def other_instance_running() -> bool:
    """True when another live TaskForge process holds the instance lock."""
    existing = _lock_pid()
    return existing is not None and existing != os.getpid() and is_pid_running(existing)


def acquire() -> bool:
    """Return True if this process should continue as the primary GUI instance."""
    existing = _lock_pid()
    if existing is not None and existing != os.getpid() and is_pid_running(existing):
        return False

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(
            os.getpid()
        ):
            LOCK_FILE.unlink()
    except OSError:
        pass
