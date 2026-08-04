# Task registry — in-memory index backed by SQLite.

from __future__ import annotations

import json
from typing import Iterable

from loguru import logger

from database.database import get_session
from database.models import TaskRecord
from runtime.task import Task


class TaskRegistry:
    """Keeps Task objects in memory and syncs them to the database."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def load(self) -> None:
        """Load all tasks from the database into memory."""
        self._tasks.clear()
        session = get_session()
        try:
            records = session.query(TaskRecord).order_by(TaskRecord.name).all()
            for record in records:
                task = self._from_record(record)
                self._tasks[task.name] = task
            logger.info("Loaded {} task(s) from database", len(self._tasks))
        finally:
            session.close()

    def list_tasks(self) -> list[Task]:
        return sorted(self._tasks.values(), key=lambda task: task.name.lower())

    def get(self, name: str) -> Task | None:
        return self._tasks.get(name)

    def get_by_id(self, task_id: int) -> Task | None:
        for task in self._tasks.values():
            if task.id == task_id:
                return task
        return None

    def add(self, task: Task, persist: bool = True) -> Task:
        """Register a task. Raises ValueError if the name already exists."""
        if task.name in self._tasks:
            raise ValueError(f"Task already exists: {task.name!r}")

        if persist:
            session = get_session()
            try:
                record = TaskRecord(
                    name=task.name,
                    description=task.description,
                    enabled=task.enabled,
                    command=task.command,
                    target=task.target,
                    schedule_json=json.dumps(task.schedule),
                    args_json=json.dumps(task.args),
                    last_run=task.last_run,
                    next_run=task.next_run,
                    status=task.status,
                    duration=task.duration,
                    failures=task.failures,
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                task.id = record.id
            finally:
                session.close()

        self._tasks[task.name] = task
        logger.info("Added task: {}", task.name)
        return task

    def update(self, task: Task) -> Task:
        """Persist changes for an existing task."""
        if task.id is None:
            raise ValueError("Cannot update a task without a database id")

        session = get_session()
        try:
            record = session.get(TaskRecord, task.id)
            if record is None:
                raise ValueError(f"Task id {task.id} not found in database")

            old_name = record.name
            record.name = task.name
            record.description = task.description
            record.enabled = task.enabled
            record.command = task.command
            record.target = task.target
            record.schedule_json = json.dumps(task.schedule)
            record.args_json = json.dumps(task.args)
            record.last_run = task.last_run
            record.next_run = task.next_run
            record.status = task.status
            record.duration = task.duration
            record.failures = task.failures
            session.commit()

            if old_name != task.name and old_name in self._tasks:
                del self._tasks[old_name]
            self._tasks[task.name] = task
        finally:
            session.close()

        return task

    def remove(self, name: str) -> None:
        task = self._tasks.get(name)
        if task is None:
            raise ValueError(f"Task not found: {name!r}")

        session = get_session()
        try:
            if task.id is not None:
                record = session.get(TaskRecord, task.id)
                if record is not None:
                    session.delete(record)
                    session.commit()
        finally:
            session.close()

        del self._tasks[name]
        logger.info("Removed task: {}", name)

    def enabled_tasks(self) -> Iterable[Task]:
        return (task for task in self._tasks.values() if task.enabled)

    @staticmethod
    def _from_record(record: TaskRecord) -> Task:
        schedule = json.loads(record.schedule_json or "{}")
        args = json.loads(record.args_json or "[]")
        return Task(
            id=record.id,
            name=record.name,
            description=record.description or "",
            enabled=bool(record.enabled),
            command=record.command,
            target=record.target,
            schedule=schedule,
            args=args,
            status=record.status or "idle",
            last_run=record.last_run,
            next_run=record.next_run,
            duration=record.duration,
            failures=record.failures or 0,
        )
