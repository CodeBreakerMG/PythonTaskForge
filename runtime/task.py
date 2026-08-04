# Task Contract Module

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

# Accept "monday" or "mondays"
WEEKDAY_ALIASES = {day: day for day in WEEKDAYS}
WEEKDAY_ALIASES.update({f"{day}s": day for day in WEEKDAYS})

DEFAULT_SCHEDULE = {
    "type": "manual",
    "hours": 0,
    "minutes": 0,
    "days": [],
    "dates": [],
    "cron": "",
}


class Task:
    """A single automation job. Create instances — do not subclass."""

    def __init__(
        self,
        name: str,
        description: str = "",
        enabled: bool = True,
        command: str | None = None,
        target: str | None = None,
        string_schedule: str | None = None,
        schedule: dict[str, Any] | None = None,
        args: list[Any] | None = None,
        id: int | None = None,
        status: str = "idle",
        last_run: datetime | None = None,
        next_run: datetime | None = None,
        duration: float | None = None,
        failures: int = 0,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.enabled = enabled
        self.command = command
        self.target = target
        self.args = list(args or [])
        self.status = status
        self.last_run = last_run
        self.next_run = next_run
        self.duration = duration
        self.failures = failures

        if schedule is not None:
            self.schedule = {
                "type": schedule.get("type", "manual"),
                "hours": schedule.get("hours", 0),
                "minutes": schedule.get("minutes", 0),
                "days": list(schedule.get("days") or []),
                "dates": list(schedule.get("dates") or []),
                "cron": schedule.get("cron", ""),
            }
        else:
            self.schedule = DEFAULT_SCHEDULE.copy()
            self.schedule["days"] = []
            self.schedule["dates"] = []
            self.update_schedule(string_schedule)

    def update_schedule(self, string_schedule: str | None) -> None:
        """
        Parse a human schedule string into self.schedule.

        Examples:
          - "manual"
          - "daily 6:00PM"
          - "daily at 6 PM"
          - "mondays and thursdays at 4 PM"
          - "monday, friday at 9:30AM"
          - "3/31/2026 at 4 PM"
          - "3/31/2026 and 4/15/2026 at 4 PM"
        """
        if not string_schedule or not string_schedule.strip():
            self._set_manual_schedule()
            return

        text = " ".join(string_schedule.strip().lower().split())

        if text == "manual":
            self._set_manual_schedule()
            return

        # once / multi-date: "3/31/2026 at 4 PM" or "3/31/2026 and 4/15/2026 at 4 PM"
        date_matches = re.findall(r"\d{1,2}/\d{1,2}/\d{4}", text)
        time_match = re.search(
            r"\bat\s+(\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})",
            text,
        )
        if date_matches and time_match:
            hours, minutes = self._parse_time(time_match.group(1))
            dates = [
                datetime.strptime(raw, "%m/%d/%Y").strftime("%Y-%m-%d")
                for raw in date_matches
            ]
            self.schedule = {
                "type": "once",
                "hours": hours,
                "minutes": minutes,
                "days": [],
                "dates": dates,
                "cron": "",
            }
            return

        # daily: "daily 6:00PM" / "daily at 6 PM" / "daily 18:00"
        daily_match = re.match(
            r"^daily(?:\s+at)?\s+(\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})$",
            text,
        )
        if daily_match:
            hours, minutes = self._parse_time(daily_match.group(1))
            self.schedule = {
                "type": "daily",
                "hours": hours,
                "minutes": minutes,
                "days": WEEKDAYS.copy(),
                "dates": [],
                "cron": f"{minutes} {hours} * * *",
            }
            return

        # weekly natural language:
        # "mondays and thursdays at 4 PM"
        # "monday, friday at 9:30AM"
        weekly_match = re.match(
            r"^(.+?)\s+at\s+(\d{1,2}(?::\d{2})?\s*[ap]m|\d{1,2}:\d{2})$",
            text,
        )
        if weekly_match:
            days_part, time_str = weekly_match.groups()
            days = self._parse_days(days_part)
            if days:
                hours, minutes = self._parse_time(time_str)
                cron_days = ",".join(str(WEEKDAYS.index(day)) for day in days)
                self.schedule = {
                    "type": "weekly",
                    "hours": hours,
                    "minutes": minutes,
                    "days": days,
                    "dates": [],
                    "cron": f"{minutes} {hours} * * {cron_days}",
                }
                return

        raise ValueError(f"Could not understand schedule: {string_schedule!r}")

    def _set_manual_schedule(self) -> None:
        self.schedule = {
            "type": "manual",
            "hours": 0,
            "minutes": 0,
            "days": [],
            "dates": [],
            "cron": "",
        }

    def _parse_days(self, days_part: str) -> list[str]:
        cleaned = days_part.replace(" and ", " ").replace(",", " ")
        words = [word.strip() for word in cleaned.split() if word.strip()]
        days: list[str] = []
        for word in words:
            if word in WEEKDAY_ALIASES:
                day = WEEKDAY_ALIASES[word]
                if day not in days:
                    days.append(day)
        return days

    def _parse_time(self, value: str) -> tuple[int, int]:
        """Accepts 4 PM, 4:00PM, 18:00. Returns 24-hour (hours, minutes)."""
        normalized = value.strip().lower().replace(" ", "").upper()
        for fmt in ("%I:%M%p", "%I%p", "%H:%M"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                return parsed.hour, parsed.minute
            except ValueError:
                continue
        raise ValueError(f'Invalid time: {value!r}. Use "4 PM", "4:00PM", or "16:00".')

    def execute(self) -> Any:
        """Execute the task. Filled in later by the executor."""
        pass

    def modify(
        self,
        name: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
        command: str | None = None,
        target: str | None = None,
        schedule: dict[str, Any] | str | None = None,
        args: list[Any] | None = None,
    ) -> None:
        """Update task fields. Pass a schedule dict or a schedule string."""
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if enabled is not None:
            self.enabled = enabled
        if command is not None:
            self.command = command
        if target is not None:
            self.target = target
        if schedule is not None:
            if isinstance(schedule, str):
                self.update_schedule(schedule)
            else:
                self.schedule = schedule
        if args is not None:
            self.args = args

    def deactivate(self) -> None:
        """Disable the task."""
        self.enabled = False

    def activate(self) -> None:
        """Enable the task."""
        self.enabled = True

    def schedule_as_string(self) -> str:
        """Rebuild a human schedule string from the stored schedule dict."""
        schedule = self.schedule or {}
        schedule_type = (schedule.get("type") or "manual").lower()
        hours = int(schedule.get("hours") or 0)
        minutes = int(schedule.get("minutes") or 0)
        time_24 = f"{hours:02d}:{minutes:02d}"

        if schedule_type == "manual":
            return "manual"
        if schedule_type == "daily":
            return f"daily {time_24}"
        if schedule_type == "weekly":
            days = schedule.get("days") or []
            if not days:
                return f"daily {time_24}"
            return f"{', '.join(days)} at {time_24}"
        if schedule_type == "once":
            dates = []
            for raw in schedule.get("dates") or []:
                try:
                    dt = datetime.strptime(raw, "%Y-%m-%d")
                    dates.append(f"{dt.month}/{dt.day}/{dt.year}")
                except ValueError:
                    dates.append(raw)
            if not dates:
                return "manual"
            return f"{' and '.join(dates)} at {time_24}"
        if schedule.get("cron"):
            return f"daily {time_24}"
        return "manual"

    def __str__(self) -> str:
        return (
            f"Task(name={self.name!r}, description={self.description!r}, "
            f"enabled={self.enabled}, command={self.command!r}, "
            f"target={self.target!r}, schedule={self.schedule}, args={self.args})"
        )
