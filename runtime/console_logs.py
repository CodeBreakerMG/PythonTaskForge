# Per-task console log files — line-by-line output while jobs run.

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


def console_log_path(task_id: int, task_name: str = "") -> Path:
    slug = safe_task_slug(task_name)
    return console_logs_dir() / f"{task_id}_{slug}.log"


def append_console_line(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else line + "\n")
        handle.flush()


def append_console_marker(log_path: Path, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_console_line(log_path, f"======== {message} @ {stamp} ========")


def read_console_log(task_id: int, task_name: str = "", *, max_chars: int = 200_000) -> str:
    path = console_log_path(task_id, task_name)
    if not path.exists():
        return f"(No console log yet for this task.)\nExpected file:\n{path}"

    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return (
            f"... (showing last {max_chars} characters) ...\n\n"
            + text[-max_chars:]
        )
    return text


def clear_console_log(task_id: int, task_name: str = "") -> None:
    path = console_log_path(task_id, task_name)
    if path.exists():
        path.write_text("", encoding="utf-8")
