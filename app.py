#!/usr/bin/env python3
"""TaskForge entrypoint — starts the runtime and desktop dashboard."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when launched as a script.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def is_supervised_startup(start_in_background: bool) -> bool:
    """True when this process is already the launchd-managed background instance."""
    if not start_in_background:
        return False
    from runtime.launchd_agent import is_supervised_by_launchd

    return is_supervised_by_launchd()


def run_gui(*, start_in_background: bool = False) -> int:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from config.settings import load_settings
    from gui.main_window import MainWindow
    from runtime.launchd_agent import handoff_to_launchd_supervision, prepare_crash_recovery
    from runtime.service import TaskForgeService
    from runtime.single_instance import acquire, release

    if not acquire():
        return 0

    settings = load_settings()
    if settings.keep_running_in_tray and not is_supervised_startup(start_in_background):
        ok, message, needs_handoff = prepare_crash_recovery()
        if not ok:
            print(message, file=sys.stderr)
        elif needs_handoff:
            release()
            ok, message = handoff_to_launchd_supervision()
            if not ok:
                print(message, file=sys.stderr)
            return 0
    service = TaskForgeService()
    service.start()

    app = QApplication(sys.argv)
    app.setApplicationName("TaskForge")
    app.setQuitOnLastWindowClosed(not settings.keep_running_in_tray)
    app.aboutToQuit.connect(release)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "Warning: system tray is unavailable; closing the window will quit TaskForge.",
            file=sys.stderr,
        )

    window = MainWindow(service)
    if settings.keep_running_in_tray:
        window.install_dock_reopen_handlers()

    if start_in_background and settings.keep_running_in_tray:
        if window.tray is not None:
            window.hide()
            from runtime.notifications import notify

            notify(
                "TaskForge restarted",
                "Recovered after an unexpected exit. Use the menu-bar TF icon to reopen.",
            )
        else:
            window.show()
    else:
        window.show()
    code = app.exec()
    service.stop()
    return code


def run_once(task_name: str) -> int:
    from runtime.service import TaskForgeService

    service = TaskForgeService()
    service.start()
    try:
        result = service.run_task(task_name)
        print(f"[{result.status}] {task_name} ({result.duration:.2f}s)")
        if result.output:
            print(result.output)
        if result.error:
            print(result.error, file=sys.stderr)
        return 0 if result.ok else 1
    finally:
        service.stop()


def list_tasks() -> int:
    from runtime.service import TaskForgeService

    service = TaskForgeService()
    service.start()
    try:
        tasks = service.registry.list_tasks()
        if not tasks:
            print("No tasks registered.")
            return 0
        for task in tasks:
            schedule = task.schedule.get("type", "manual")
            print(
                f"- {task.name} | enabled={task.enabled} | "
                f"status={task.status} | schedule={schedule}"
            )
        return 0
    finally:
        service.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="TaskForge automation runtime")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered tasks and exit",
    )
    parser.add_argument(
        "--run",
        metavar="TASK",
        help="Run a task by name (no GUI) and exit",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start without opening the dashboard (used by launchd)",
    )
    args = parser.parse_args()

    if args.list:
        return list_tasks()
    if args.run:
        return run_once(args.run)
    return run_gui(start_in_background=args.background)


if __name__ == "__main__":
    raise SystemExit(main())
