# Per-run console log files — line-by-line output while jobs run.

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from config.settings import app_support_dir

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def console_logs_dir() -> Path:
    path = app_support_dir() / "console_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_task_slug(name: str) -> str:
    slug = _UNSAFE.sub("_", (name or "task").strip()).strip("._")
    return slug or "task"


def task_console_dir(task_id: int, task_name: str = "", *, create: bool = True) -> Path:
    path = console_logs_dir() / f"{task_id}_{safe_task_slug(task_name)}"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def console_log_path(
    task_id: int,
    task_name: str = "",
    *,
    history_id: int,
    started: datetime | None = None,
) -> Path:
    stamp = (started or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return task_console_dir(task_id, task_name) / f"{stamp}_{history_id}.log"


def latest_console_log(task_id: int, task_name: str = "") -> Path | None:
    folder = task_console_dir(task_id, task_name, create=False)
    if not folder.exists():
        return None
    files = sorted(folder.glob("*.log"))
    return files[-1] if files else None


def append_console_line(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else line + "\n")
        handle.flush()


def append_console_marker(log_path: Path, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_console_line(log_path, f"======== {message} @ {stamp} ========")


def read_console_log(task_id: int, task_name: str = "", *, max_chars: int = 200_000) -> str:
    folder = task_console_dir(task_id, task_name, create=False)
    path = latest_console_log(task_id, task_name)
    if path is None:
        return f"(No console log yet for this task.)\nExpected folder:\n{folder}"

    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return (
            f"... (showing last {max_chars} characters) ...\n\n"
            + text[-max_chars:]
        )
    return text


def clear_console_log(task_id: int, task_name: str = "") -> None:
    folder = task_console_dir(task_id, task_name, create=False)
    if not folder.exists():
        return
    for path in folder.glob("*.log"):
        path.write_text("", encoding="utf-8")
