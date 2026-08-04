# Scheduler — APScheduler integration for TaskForge.

from __future__ import annotations

from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from runtime.registry import TaskRegistry
from runtime.task import Task


class TaskScheduler:
    """Registers enabled tasks with APScheduler."""

    def __init__(
        self,
        registry: TaskRegistry,
        on_run: Callable[[Task], None],
    ) -> None:
        self.registry = registry
        self.on_run = on_run
        self._scheduler = BackgroundScheduler()
        self._started = False

    @property
    def running(self) -> bool:
        return self._started and self._scheduler.running

    def start(self) -> None:
        if self._started:
            return
        self.reload()
        self._scheduler.start()
        self._started = True
        logger.info("Scheduler started")

    def shutdown(self) -> None:
        if not self._started:
            return
        self._scheduler.shutdown(wait=False)
        self._started = False
        logger.info("Scheduler stopped")

    def reload(self) -> None:
        """Clear jobs and re-register all enabled, non-manual tasks."""
        self._scheduler.remove_all_jobs()
        for task in self.registry.enabled_tasks():
            self._schedule_task(task)
        logger.info("Scheduler loaded {} job(s)", len(self._scheduler.get_jobs()))

    def _schedule_task(self, task: Task) -> None:
        schedule = task.schedule or {}
        schedule_type = (schedule.get("type") or "manual").lower()

        if schedule_type == "manual" or not task.enabled:
            return

        if schedule_type == "once":
            hours = int(schedule.get("hours") or 0)
            minutes = int(schedule.get("minutes") or 0)
            for index, date_str in enumerate(schedule.get("dates") or []):
                try:
                    day = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    logger.warning("Invalid date on task {}: {}", task.name, date_str)
                    continue
                run_at = day.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                if run_at <= datetime.now():
                    logger.debug("Skipping past once-date {} for {}", run_at, task.name)
                    continue
                job_id = f"task-{task.id}-once-{index}"
                self._scheduler.add_job(
                    self._fire,
                    trigger=DateTrigger(run_date=run_at),
                    id=job_id,
                    replace_existing=True,
                    kwargs={"task_name": task.name},
                    name=f"{task.name} @ {run_at.isoformat()}",
                )
            return

        cron_expr = (schedule.get("cron") or "").strip()
        if cron_expr:
            parts = cron_expr.split()
            if len(parts) != 5:
                logger.warning("Invalid cron for {}: {}", task.name, cron_expr)
                return
            minute, hour, day, month, day_of_week = parts
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
        elif schedule_type in {"daily", "weekly"}:
            weekdays = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            if schedule_type == "weekly" and schedule.get("days"):
                day_of_week = ",".join(
                    str(weekdays.index(day)) for day in schedule["days"] if day in weekdays
                )
            else:
                day_of_week = "*"
            trigger = CronTrigger(
                minute=int(schedule.get("minutes") or 0),
                hour=int(schedule.get("hours") or 0),
                day_of_week=day_of_week,
            )
        else:
            logger.warning("Unsupported schedule type for {}: {}", task.name, schedule_type)
            return

        job_id = f"task-{task.id}"
        self._scheduler.add_job(
            self._fire,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs={"task_name": task.name},
            name=task.name,
        )
        logger.debug("Scheduled {} ({})", task.name, schedule_type)

    def _fire(self, task_name: str) -> None:
        task = self.registry.get(task_name)
        if task is None:
            logger.warning("Scheduled fire for unknown task: {}", task_name)
            return
        if not task.enabled:
            logger.info("Skipping disabled task: {}", task_name)
            return
        self.on_run(task)
