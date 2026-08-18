# Task executor — runs a Task and records history.

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from database.database import get_session
from database.models import History, Log, TaskRecord
from runtime.console_logs import (
    append_console_line,
    append_console_marker,
    console_log_path,
)
from runtime.task import Task

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ExecutionResult:
    def __init__(
        self,
        status: str,
        output: str = "",
        error: str = "",
        duration: float = 0.0,
        history_id: int | None = None,
        console_log: Path | None = None,
    ) -> None:
        self.status = status
        self.output = output
        self.error = error
        self.duration = duration
        self.history_id = history_id
        self.console_log = console_log

    @property
    def ok(self) -> bool:
        return self.status == "success"


class Executor:
    """Runs tasks and writes execution history to the database."""

    def run(self, task: Task) -> ExecutionResult:
        if task.id is None:
            raise ValueError(f"Task {task.name!r} has no database id")

        started = datetime.utcnow()
        log_path = console_log_path(task.id, task.name)
        session = get_session()
        history = History(
            task_id=task.id,
            started=started,
            status="running",
            log="",
        )
        try:
            record = session.get(TaskRecord, task.id)
            if record is None:
                raise ValueError(f"Task id {task.id} not found")
            record.status = "running"
            session.add(history)
            session.commit()
            session.refresh(history)
            history_id = history.id
        finally:
            session.close()

        append_console_marker(log_path, f"RUN START — {task.name}")
        logger.info("Running task: {} (console log: {})", task.name, log_path)
        output = ""
        error = ""
        status = "success"

        try:
            output = self._execute(task, log_path)
        except Exception as exc:
            status = "failed"
            error = f"{exc}\n{traceback.format_exc()}"
            append_console_line(log_path, error)
            logger.error("Task failed: {} — {}", task.name, exc)

        ended = datetime.utcnow()
        duration = (ended - started).total_seconds()
        combined_log = output
        if error:
            combined_log = (combined_log + "\n" + error).strip()

        append_console_marker(
            log_path,
            f"RUN END — {status} ({duration:.2f}s)",
        )
        append_console_line(log_path, "")

        session = get_session()
        try:
            history = session.get(History, history_id)
            record = session.get(TaskRecord, task.id)
            if history is not None:
                history.ended = ended
                history.duration = duration
                history.status = status
                history.log = combined_log

            if record is not None:
                record.last_run = ended
                record.duration = duration
                record.status = status
                if status == "failed":
                    record.failures = (record.failures or 0) + 1

            session.add(
                Log(
                    task_id=task.id,
                    timestamp=ended,
                    level="ERROR" if status == "failed" else "INFO",
                    message=combined_log or f"Task {task.name} finished with {status}",
                )
            )
            session.commit()
        finally:
            session.close()

        task.last_run = ended
        task.duration = duration
        task.status = status
        if status == "failed":
            task.failures += 1

        return ExecutionResult(
            status=status,
            output=output,
            error=error,
            duration=duration,
            history_id=history_id,
            console_log=log_path,
        )

    def _execute(self, task: Task, log_path: Path) -> str:
        command = (task.command or "").strip().lower()
        target = (task.target or "").strip()
        if not target:
            raise ValueError("Task has no target to execute")

        args = [str(arg) for arg in (task.args or [])]

        # People often paste "python3 /path/to/script.py" into Target.
        # For Action=script, Target should be only the .py path.
        script_candidate = self._extract_script_path(target)
        if command in {"", "script", "python"} or script_candidate.endswith(".py"):
            script_path = self._resolve_path(script_candidate)
            if not script_path.exists():
                raise FileNotFoundError(
                    f"Script not found: {script_path}\n"
                    "For Action=script, Target must be the .py file path only "
                    "(example: /Users/you/project/script.py)."
                )
            return self._run_subprocess(
                [sys.executable, "-u", str(script_path), *args],
                log_path=log_path,
            )

        if command in {"command", "shell", "bash"}:
            return self._run_subprocess(target, shell=True, log_path=log_path)

        # Fallback: treat target as a shell command string.
        full = " ".join([target, *args]).strip()
        return self._run_subprocess(full, shell=True, log_path=log_path)

    def _extract_script_path(self, target: str) -> str:
        """Strip leading python/python3 from a pasted command line."""
        text = target.strip().strip('"').strip("'")
        lowered = text.lower()
        for prefix in ("python3 ", "python ", "py "):
            if lowered.startswith(prefix):
                return text[len(prefix):].strip().strip('"').strip("'")
        return text

    def _resolve_path(self, target: str) -> Path:
        path = Path(target).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    def _run_subprocess(
        self,
        cmd: Any,
        *,
        shell: bool = False,
        log_path: Path,
    ) -> str:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(PROJECT_ROOT),
            env=env,
        )

        collected: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            collected.append(line.rstrip("\n"))
            append_console_line(log_path, line)

        return_code = process.wait()
        output = "\n".join(collected).strip()
        if return_code != 0:
            raise RuntimeError(
                f"Command exited with code {return_code}\n{output}"
            )
        return output
