# Main TaskForge desktop window.

from __future__ import annotations

import subprocess

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config.settings import load_settings
from gui.settings_dialog import SettingsDialog
from gui.task_editor import TaskEditorDialog
from gui.tray import TaskForgeTray
from runtime.launchd_agent import handoff_to_launchd_supervision, sync_crash_recovery_agent
from runtime.notifications import set_tray_hook
from runtime.service import TaskForgeService
from runtime.single_instance import release


class _RunTaskWorker(QThread):
    finished_ok = Signal(object)
    finished_error = Signal(str)

    def __init__(self, service: TaskForgeService, task_name: str) -> None:
        super().__init__()
        self._service = service
        self._task_name = task_name

    def run(self) -> None:
        try:
            result = self._service.run_task(self._task_name)
            self.finished_ok.emit(result)
        except Exception as exc:
            self.finished_error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, service: TaskForgeService) -> None:
        super().__init__()
        self.service = service
        self._force_quit = False
        self._keep_running_in_tray = load_settings().keep_running_in_tray
        self._dock_filter: QObject | None = None
        self._viewing_task: str | None = None
        self._run_worker: _RunTaskWorker | None = None
        self.setWindowTitle("TaskForge")
        self.resize(1000, 720)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        header = QLabel("TaskForge")
        header.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(header)

        subtitle = QLabel("Local automation runtime — tasks, runs, and history")
        subtitle.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        buttons = QHBoxLayout()
        self.create_btn = QPushButton("Create Task")
        self.modify_btn = QPushButton("Modify")
        self.run_btn = QPushButton("Run Selected")
        self.enable_btn = QPushButton("Enable")
        self.disable_btn = QPushButton("Disable")
        self.delete_btn = QPushButton("Delete")
        self.settings_btn = QPushButton("Settings")
        self.refresh_btn = QPushButton("Refresh")
        for button in (
            self.create_btn,
            self.modify_btn,
            self.run_btn,
            self.enable_btn,
            self.disable_btn,
            self.delete_btn,
            self.settings_btn,
            self.refresh_btn,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, stretch=1)

        self.task_table = QTableWidget(0, 6)
        self.task_table.setHorizontalHeaderLabels(
            ["Name", "Status", "Schedule", "Last Run", "Enabled", "Failures"]
        )
        self.task_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.task_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.task_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.task_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.task_table)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(QLabel("Recent History"))
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["Task", "Started", "Duration", "Status", "Log"]
        )
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        bottom_layout.addWidget(self.history_table)

        console_header = QHBoxLayout()
        self.console_label = QLabel("Console output — select a task")
        console_header.addWidget(self.console_label, stretch=1)
        self.reload_console_btn = QPushButton("Reload Log")
        self.open_logs_btn = QPushButton("Show in Finder")
        console_header.addWidget(self.reload_console_btn)
        console_header.addWidget(self.open_logs_btn)
        bottom_layout.addLayout(console_header)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(180)
        mono = QFont("Menlo")
        if not mono.exactMatch():
            mono = QFont("Courier New")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPointSize(11)
        self.output.setFont(mono)
        bottom_layout.addWidget(self.output)
        splitter.addWidget(bottom)
        splitter.setSizes([280, 360])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self.create_btn.clicked.connect(self._create_task)
        self.modify_btn.clicked.connect(self._modify_selected)
        self.run_btn.clicked.connect(self._run_selected)
        self.enable_btn.clicked.connect(lambda: self._set_enabled(True))
        self.disable_btn.clicked.connect(lambda: self._set_enabled(False))
        self.delete_btn.clicked.connect(self._delete_selected)
        self.settings_btn.clicked.connect(self._open_settings)
        self.refresh_btn.clicked.connect(self.refresh)
        self.reload_console_btn.clicked.connect(self._reload_selected_console)
        self.open_logs_btn.clicked.connect(self._open_selected_logs_in_finder)
        self.task_table.itemSelectionChanged.connect(self._on_task_selected)

        self.tray: TaskForgeTray | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = TaskForgeTray(self)
            self.tray.open_requested.connect(self.show_from_tray)
            self.tray.quit_requested.connect(self.quit_app)
            set_tray_hook(self.tray.show_message)
            self._update_tray_status_message()
        else:
            set_tray_hook(None)
            self.statusBar().showMessage("Ready")

        self._console_timer = QTimer(self)
        self._console_timer.setInterval(1000)
        self._console_timer.timeout.connect(self._poll_console_log)
        self._console_timer.start()

        self.refresh()

    def install_dock_reopen_handlers(self) -> None:
        app = QApplication.instance()
        if app is None or self._dock_filter is not None:
            return

        window = self

        class _DockReopenFilter(QObject):
            def eventFilter(self, obj, event):  # noqa: N802
                if event.type() == QEvent.Type.ApplicationActivate:
                    if (
                        not window._force_quit
                        and window._keep_running_in_tray
                        and not window.isVisible()
                    ):
                        window.show_from_tray()
                return super().eventFilter(obj, event)

        self._dock_filter = _DockReopenFilter(self)
        app.installEventFilter(self._dock_filter)
        app.applicationStateChanged.connect(self._on_app_state_changed)

    def remove_dock_reopen_handlers(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        if self._dock_filter is not None:
            app.removeEventFilter(self._dock_filter)
            self._dock_filter = None
        try:
            app.applicationStateChanged.disconnect(self._on_app_state_changed)
        except TypeError:
            pass

    def _on_app_state_changed(self, state) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            if (
                not self._force_quit
                and self._keep_running_in_tray
                and not self.isVisible()
            ):
                self.show_from_tray()

    def refresh(self) -> None:
        selected = self._selected_task_name()
        tasks = self.service.registry.list_tasks()
        self.task_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            schedule = task.schedule or {}
            schedule_label = schedule.get("type", "manual")
            if schedule.get("cron"):
                schedule_label = f"{schedule_label} ({schedule['cron']})"
            elif schedule.get("dates"):
                schedule_label = f"{schedule_label}: {', '.join(schedule['dates'])}"

            last_run = (
                task.last_run.isoformat(sep=" ", timespec="seconds")
                if task.last_run
                else "—"
            )
            values = [
                task.name,
                task.status,
                schedule_label,
                last_run,
                "yes" if task.enabled else "no",
                str(task.failures),
            ]
            for col, value in enumerate(values):
                self.task_table.setItem(row, col, QTableWidgetItem(value))

        if selected:
            for row in range(self.task_table.rowCount()):
                item = self.task_table.item(row, 0)
                if item and item.text() == selected:
                    self.task_table.selectRow(row)
                    break

        history = self.service.recent_history(limit=30)
        self.history_table.setRowCount(len(history))
        for row, item in enumerate(history):
            started = (
                item["started"].isoformat(sep=" ", timespec="seconds")
                if item["started"]
                else "—"
            )
            duration = (
                f"{item['duration']:.2f}s" if item["duration"] is not None else "—"
            )
            log_preview = (item["log"] or "").replace("\n", " ")[:120]
            values = [
                item["task_name"],
                started,
                duration,
                item["status"],
                log_preview,
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(row, col, QTableWidgetItem(value))

        self.statusBar().showMessage(f"{len(tasks)} task(s) loaded")
        if selected:
            self._show_console_for(selected)

    def _selected_task_name(self) -> str | None:
        rows = self.task_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.task_table.item(rows[0].row(), 0)
        return item.text() if item else None

    def _on_task_selected(self) -> None:
        name = self._selected_task_name()
        if name:
            self._show_console_for(name)
        else:
            self._viewing_task = None
            self.console_label.setText("Console output — select a task")
            self.output.setPlainText("")

    def _reload_selected_console(self) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Console", "Select a task first.")
            return
        self._show_console_for(name)

    def _open_selected_logs_in_finder(self) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Logs", "Select a task first.")
            return
        folder = self.service.console_log_dir(name)
        if folder is None:
            QMessageBox.warning(self, "Logs", "Task has no log folder yet.")
            return
        folder.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["open", str(folder)], check=False)
        except OSError as exc:
            QMessageBox.critical(self, "Logs", f"Could not open Finder:\n{exc}")

    def _show_console_for(self, name: str) -> None:
        self._viewing_task = name
        log_file = self.service.console_log_file(name) or self.service.console_log_dir(name)
        path_note = f" — {log_file}" if log_file else ""
        self.console_label.setText(f"Console output — {name}{path_note}")
        try:
            text = self.service.get_console_log(name)
        except Exception as exc:
            text = f"(Could not read console log: {exc})"
        scrollbar = self.output.verticalScrollBar()
        stick_bottom = scrollbar.value() >= scrollbar.maximum() - 20
        self.output.setPlainText(text)
        if stick_bottom:
            self.output.moveCursor(QTextCursor.MoveOperation.End)

    def _poll_console_log(self) -> None:
        if not self.isVisible() or not self._viewing_task:
            return
        self._show_console_for(self._viewing_task)

    def _create_task(self) -> None:
        dialog = TaskEditorDialog(self)
        if dialog.exec() != TaskEditorDialog.DialogCode.Accepted:
            return
        task = dialog.task()
        if task is None:
            return
        try:
            self.service.add_task(task)
            self.refresh()
            self.statusBar().showMessage(f"Created task: {task.name}")
            self._show_console_for(task.name)
        except Exception as exc:
            QMessageBox.critical(self, "Create Failed", str(exc))

    def _modify_selected(self) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Modify Task", "Select a task first.")
            return
        existing = self.service.registry.get(name)
        if existing is None:
            QMessageBox.warning(self, "Modify Task", f"Task not found: {name}")
            return

        dialog = TaskEditorDialog(self, task=existing)
        if dialog.exec() != TaskEditorDialog.DialogCode.Accepted:
            return
        task = dialog.task()
        if task is None:
            return
        try:
            self.service.update_task(task)
            self.refresh()
            self.statusBar().showMessage(f"Updated task: {task.name}")
            self._show_console_for(task.name)
        except Exception as exc:
            QMessageBox.critical(self, "Modify Failed", str(exc))

    def _run_selected(self) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Run Task", "Select a task first.")
            return
        if self._run_worker is not None and self._run_worker.isRunning():
            QMessageBox.information(
                self,
                "Run Task",
                "A task is already running from the dashboard. Wait for it to finish.",
            )
            return

        self._show_console_for(name)
        self.run_btn.setEnabled(False)
        self.statusBar().showMessage(f"Running {name}…")

        worker = _RunTaskWorker(self.service, name)
        self._run_worker = worker
        worker.finished_ok.connect(self._on_run_finished)
        worker.finished_error.connect(self._on_run_failed)
        worker.finished.connect(lambda: self.run_btn.setEnabled(True))
        worker.start()

    def _on_run_finished(self, result) -> None:
        name = self._viewing_task or self._selected_task_name() or "task"
        self.refresh()
        if name:
            self._show_console_for(name)
        self.statusBar().showMessage(
            f"[{result.status}] {name} in {result.duration:.2f}s"
        )

    def _on_run_failed(self, message: str) -> None:
        name = self._viewing_task or self._selected_task_name()
        QMessageBox.critical(self, "Run Failed", message)
        if name:
            self._show_console_for(name)
        self.refresh()
        self.statusBar().showMessage("Run failed")

    def _set_enabled(self, enabled: bool) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Task", "Select a task first.")
            return
        try:
            self.service.set_enabled(name, enabled)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Update Failed", str(exc))

    def _delete_selected(self) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Delete Task", "Select a task first.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete Task",
            f"Delete task {name!r}? This also removes its history.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.remove_task(name)
            self._viewing_task = None
            self.output.setPlainText(f"Deleted task: {name}")
            self.console_label.setText("Console output — select a task")
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        saved = dialog.saved_settings()
        if saved is None:
            return

        if saved.keep_running_in_tray != self._keep_running_in_tray:
            self._apply_tray_setting(saved.keep_running_in_tray)

        try:
            current = str(self.service.database_path())
        except Exception:
            current = ""
        if saved.db_path == current:
            return
        try:
            path = self.service.set_database_path(saved.db_path)
            self.output.setPlainText(f"Using database:\n{path}")
            self.refresh()
            self.statusBar().showMessage(f"Database: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Settings Failed", str(exc))

    def _apply_tray_setting(self, keep_running: bool) -> None:
        self._keep_running_in_tray = keep_running
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(not keep_running)
        if keep_running:
            self.install_dock_reopen_handlers()
        else:
            self.remove_dock_reopen_handlers()
        ok, message, needs_handoff = sync_crash_recovery_agent(keep_running)
        if keep_running and needs_handoff and ok:
            release()
            ok, message = handoff_to_launchd_supervision()
            if ok:
                self.statusBar().showMessage(
                    "Crash recovery enabled — restarting under launchd…",
                    5000,
                )
                QTimer.singleShot(300, self.quit_app)
                return
        self._update_tray_status_message()
        if ok:
            self.statusBar().showMessage(message, 8000)
        else:
            QMessageBox.warning(self, "Background Service", message)

    def _update_tray_status_message(self) -> None:
        if self._keep_running_in_tray:
            self.statusBar().showMessage(
                "Ready — close window to keep running in the menu bar"
            )
        else:
            self.statusBar().showMessage("Ready — close window to quit TaskForge")

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh()

    def quit_app(self) -> None:
        """Fully stop the runtime and exit (from tray menu)."""
        if self._force_quit:
            return
        self._force_quit = True
        self.remove_dock_reopen_handlers()
        set_tray_hook(None)
        self.service.stop()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        # Chrome-style: X hides the window; runtime keeps going in the tray.
        if (
            not self._force_quit
            and self._keep_running_in_tray
            and self.tray is not None
        ):
            event.ignore()
            self.hide()
            from runtime.notifications import notify

            notify(
                "TaskForge is still running",
                "Click the Dock icon or the menu-bar TF icon to reopen. "
                "Use Quit TaskForge to exit.",
            )
            return

        if not self._force_quit:
            event.accept()
            self.quit_app()
            return

        set_tray_hook(None)
        self.service.stop()
        event.accept()
