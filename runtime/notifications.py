# Desktop notifications (macOS Notification Center + optional tray balloon).

from __future__ import annotations

import platform
import subprocess
from typing import Callable, Optional

from loguru import logger

from runtime.executor import ExecutionResult

_tray_hook: Optional[Callable[[str, str], None]] = None


def set_tray_hook(hook: Optional[Callable[[str, str], None]]) -> None:
    """Optional tray balloon fallback registered by the GUI."""
    global _tray_hook
    _tray_hook = hook


def notify(title: str, message: str) -> None:
    """Show a user-visible notification."""
    if _tray_hook is not None:
        try:
            _tray_hook(title, message)
        except Exception:
            logger.exception("Tray notification failed")

    if platform.system() == "Darwin":
        _notify_macos(title, message)


def notify_task_result(task_name: str, result: ExecutionResult) -> None:
    if result.ok:
        notify(
            f"{task_name} finished",
            f"Success in {result.duration:.1f}s",
        )
    else:
        detail = (result.error or result.output or "Unknown error").strip()
        detail = detail.replace("\n", " ")
        if len(detail) > 160:
            detail = detail[:157] + "..."
        notify(f"{task_name} failed", detail or "Task failed")


def _notify_macos(title: str, message: str) -> None:
    """Post to macOS Notification Center via AppleScript."""

    def _escape(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", " ")
            .replace("\r", " ")
        )

    script = (
        f'display notification "{_escape(message)}" '
        f'with title "TaskForge" subtitle "{_escape(title)}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        logger.exception("macOS notification failed")
