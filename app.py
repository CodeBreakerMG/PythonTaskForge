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


def run_gui() -> int:
    from PySide6.QtCore import QEvent, QObject, Qt
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from gui.main_window import MainWindow
    from runtime.service import TaskForgeService

    service = TaskForgeService()
    service.start()

    app = QApplication(sys.argv)
    app.setApplicationName("TaskForge")
    # Keep process alive when the main window is hidden to the tray.
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "Warning: system tray is unavailable; closing the window will quit TaskForge.",
            file=sys.stderr,
        )

    window = MainWindow(service)

    class _DockReopenFilter(QObject):
        """Re-show the dashboard when the user clicks the macOS Dock icon."""

        def eventFilter(self, obj, event):  # noqa: N802
            if event.type() == QEvent.Type.ApplicationActivate:
                if not window._force_quit and not window.isVisible():
                    window.show_from_tray()
            return super().eventFilter(obj, event)

    dock_filter = _DockReopenFilter(app)
    app.installEventFilter(dock_filter)

    def _on_app_state_changed(state) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            if not window._force_quit and not window.isVisible():
                window.show_from_tray()

    app.applicationStateChanged.connect(_on_app_state_changed)

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
    args = parser.parse_args()

    if args.list:
        return list_tasks()
    if args.run:
        return run_once(args.run)
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
