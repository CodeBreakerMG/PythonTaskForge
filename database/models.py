from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskRecord(Base):
    """Saved task definition (matches runtime.Task fields)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    command: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # store the schedule dict as JSON text
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")
    args_json: Mapped[str] = mapped_column(Text, default="[]")

    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)

    history: Mapped[List["History"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    logs: Mapped[List["Log"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class History(Base):
    """One row per execution."""

    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    started: Mapped[datetime] = mapped_column(DateTime)
    ended: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    log: Mapped[str] = mapped_column(Text, default="")

    task: Mapped["TaskRecord"] = relationship(back_populates="history")


class Log(Base):
    """Optional detailed log lines."""

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tasks.id"), nullable=True, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)

    task: Mapped[Optional["TaskRecord"]] = relationship(back_populates="logs")
