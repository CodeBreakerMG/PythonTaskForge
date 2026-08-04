# Main TaskForge desktop window.

from __future__ import annotations

from PySide6.QtCore import Qt
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

from gui.task_editor import TaskEditorDialog
from gui.tray import TaskForgeTray
from runtime.notifications import set_tray_hook
from runtime.service import TaskForgeService


class MainWindow(QMainWindow):
    def __init__(self, service: TaskForgeService) -> None:
        super().__init__()
        self.service = service
        self._force_quit = False
        self.setWindowTitle("TaskForge")
        self.resize(1000, 640)

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
        self.refresh_btn = QPushButton("Refresh")
        for button in (
            self.create_btn,
            self.modify_btn,
            self.run_btn,
            self.enable_btn,
            self.disable_btn,
            self.delete_btn,
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

        bottom_layout.addWidget(QLabel("Output"))
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(140)
        bottom_layout.addWidget(self.output)
        splitter.addWidget(bottom)
        splitter.setSizes([320, 280])

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self.create_btn.clicked.connect(self._create_task)
        self.modify_btn.clicked.connect(self._modify_selected)
        self.run_btn.clicked.connect(self._run_selected)
        self.enable_btn.clicked.connect(lambda: self._set_enabled(True))
        self.disable_btn.clicked.connect(lambda: self._set_enabled(False))
        self.delete_btn.clicked.connect(self._delete_selected)
        self.refresh_btn.clicked.connect(self.refresh)

        self.tray: TaskForgeTray | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = TaskForgeTray(self)
            self.tray.open_requested.connect(self.show_from_tray)
            self.tray.quit_requested.connect(self.quit_app)
            set_tray_hook(self.tray.show_message)
            self.statusBar().showMessage(
                "Ready — close window to keep running in the menu bar"
            )
        else:
            set_tray_hook(None)
            self.statusBar().showMessage("Ready")

        self.refresh()

    def refresh(self) -> None:
        tasks = self.service.registry.list_tasks()
        self.task_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            schedule = task.schedule or {}
            schedule_label = schedule.get("type", "manual")
            if schedule.get("cron"):
                schedule_label = f"{schedule_label} ({schedule['cron']})"
            elif schedule.get("dates"):
                schedule_label = f"{schedule_label}: {', '.join(schedule['dates'])}"

            last_run = task.last_run.isoformat(sep=" ", timespec="seconds") if task.last_run else "—"
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

        history = self.service.recent_history(limit=30)
        self.history_table.setRowCount(len(history))
        for row, item in enumerate(history):
            started = (
                item["started"].isoformat(sep=" ", timespec="seconds")
                if item["started"]
                else "—"
            )
            duration = f"{item['duration']:.2f}s" if item["duration"] is not None else "—"
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

    def _selected_task_name(self) -> str | None:
        rows = self.task_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.task_table.item(rows[0].row(), 0)
        return item.text() if item else None

    def _create_task(self) -> None:
        dialog = TaskEditorDialog(self)
        if dialog.exec() != TaskEditorDialog.DialogCode.Accepted:
            return
        task = dialog.task()
        if task is None:
            return
        try:
            self.service.add_task(task)
            self.output.setPlainText(f"Created task: {task.name}")
            self.refresh()
            self.statusBar().showMessage(f"Created task: {task.name}")
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
            self.output.setPlainText(f"Updated task: {task.name}")
            self.refresh()
            self.statusBar().showMessage(f"Updated task: {task.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Modify Failed", str(exc))

    def _run_selected(self) -> None:
        name = self._selected_task_name()
        if not name:
            QMessageBox.information(self, "Run Task", "Select a task first.")
            return
        try:
            result = self.service.run_task(name)
            self.output.setPlainText(
                f"[{result.status}] {name} in {result.duration:.2f}s\n\n"
                f"{result.output or ''}\n{result.error or ''}".strip()
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Run Failed", str(exc))

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
            self.output.setPlainText(f"Deleted task: {name}")
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", str(exc))

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh()

    def quit_app(self) -> None:
        """Fully stop the runtime and exit (from tray menu)."""
        self._force_quit = True
        self.service.stop()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        # Chrome-style: X hides the window; runtime keeps going in the tray.
        if not self._force_quit and self.tray is not None:
            event.ignore()
            self.hide()
            from runtime.notifications import notify

            notify(
                "TaskForge is still running",
                "Click the Dock icon or the menu-bar TF icon to reopen. "
                "Use Quit TaskForge to exit.",
            )
            return

        set_tray_hook(None)
        self.service.stop()
        event.accept()
