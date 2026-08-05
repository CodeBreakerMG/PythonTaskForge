# TaskForge runtime service — ties registry, executor, and scheduler together.

from __future__ import annotations

from pathlib import Path

from loguru import logger

from config.settings import AppSettings, load_settings, save_settings
from database.database import get_db_path, get_session, init_db
from database.models import History
from runtime.executor import ExecutionResult, Executor
from runtime.notifications import notify, notify_task_result
from runtime.registry import TaskRegistry
from runtime.scheduler import TaskScheduler
from runtime.task import Task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


class TaskForgeService:
    """Long-lived automation runtime."""

    def __init__(self) -> None:
        self.registry = TaskRegistry()
        self.executor = Executor()
        self.scheduler = TaskScheduler(self.registry, on_run=self._scheduled_run)
        self._started = False

    def start(self) -> None:
        if self._started:
            return

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.add(
            LOG_DIR / "taskforge.log",
            rotation="5 MB",
            retention="14 days",
            level="INFO",
        )

        settings = load_settings()
        db_path = init_db(settings.db_path)
        # Persist resolved defaults the first time so Settings shows a real path.
        save_settings(AppSettings(db_path=str(db_path)))
        self.registry.load()
        self._ensure_sample_task()
        self.scheduler.start()
        self._started = True
        logger.info("TaskForge runtime ready (db={})", db_path)

    def stop(self) -> None:
        if not self._started:
            return
        self.scheduler.shutdown()
        self._started = False
        logger.info("TaskForge runtime stopped")

    def database_path(self) -> Path:
        return get_db_path()

    def set_database_path(self, db_path: Path | str) -> Path:
        """Switch SQLite file, reload tasks, and reschedule jobs."""
        was_running = self._started
        if was_running:
            self.scheduler.shutdown()

        settings = AppSettings(db_path=str(Path(db_path).expanduser()))
        save_settings(settings)
        path = init_db(settings.db_path)
        self.registry.load()
        self._ensure_sample_task()

        if was_running:
            self.scheduler = TaskScheduler(self.registry, on_run=self._scheduled_run)
            self.scheduler.start()

        logger.info("Switched database to {}", path)
        notify("Database updated", f"Using {path}")
        return path

    def run_task(self, name: str, *, notify_user: bool = True) -> ExecutionResult:
        task = self.registry.get(name)
        if task is None:
            raise ValueError(f"Task not found: {name!r}")
        result = self.executor.run(task)
        self.registry.update(task)
        if notify_user:
            notify_task_result(task.name, result)
        return result

    def add_task(self, task: Task) -> Task:
        created = self.registry.add(task)
        self.scheduler.reload()
        return created

    def update_task(self, task: Task) -> Task:
        updated = self.registry.update(task)
        self.scheduler.reload()
        return updated

    def remove_task(self, name: str) -> None:
        self.registry.remove(name)
        self.scheduler.reload()

    def set_enabled(self, name: str, enabled: bool) -> Task:
        task = self.registry.get(name)
        if task is None:
            raise ValueError(f"Task not found: {name!r}")
        if enabled:
            task.activate()
        else:
            task.deactivate()
        self.registry.update(task)
        self.scheduler.reload()
        return task

    def recent_history(self, limit: int = 50, task_name: str | None = None) -> list[dict]:
        session = get_session()
        try:
            query = session.query(History).order_by(History.started.desc())
            if task_name:
                task = self.registry.get(task_name)
                if task is None or task.id is None:
                    return []
                query = query.filter(History.task_id == task.id)
            rows = query.limit(limit).all()
            results = []
            for row in rows:
                task = self.registry.get_by_id(row.task_id)
                results.append(
                    {
                        "id": row.id,
                        "task_id": row.task_id,
                        "task_name": task.name if task else f"#{row.task_id}",
                        "started": row.started,
                        "ended": row.ended,
                        "duration": row.duration,
                        "status": row.status,
                        "log": row.log or "",
                    }
                )
            return results
        finally:
            session.close()

    def _scheduled_run(self, task: Task) -> None:
        try:
            result = self.executor.run(task)
            self.registry.update(task)
            notify_task_result(task.name, result)
            logger.info(
                "Scheduled run finished: {} ({})",
                task.name,
                result.status,
            )
        except Exception as exc:
            logger.exception("Scheduled run crashed for {}", task.name)
            notify(f"{task.name} crashed", str(exc)[:160])

    def _ensure_sample_task(self) -> None:
        """Create a hello sample task on first launch if the DB is empty."""
        if self.registry.list_tasks():
            return

        sample = Task(
            name="Hello TaskForge",
            description="Sample smoke-test task that prints a hello message",
            enabled=True,
            command="script",
            target="tasks/hello.py",
            string_schedule="manual",
        )
        self.registry.add(sample)
        logger.info("Seeded sample task: {}", sample.name)
