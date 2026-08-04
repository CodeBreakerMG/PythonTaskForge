# Dialog for creating or modifying a TaskForge task.

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from runtime.task import Task


class TaskEditorDialog(QDialog):
    """Collect fields for a new or existing Task."""

    def __init__(self, parent=None, task: Task | None = None) -> None:
        super().__init__(parent)
        self._original = task
        self._task: Task | None = None
        self.setWindowTitle("Modify Task" if task is not None else "Create Task")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Action=script → Target is the .py path only "
            "(not “python3 …”).\n"
            "Action=command → Target is a full shell command.\n"
            "Schedule examples: manual · daily 6:00PM · "
            "mondays and thursdays at 4 PM · 3/31/2026 at 4 PM"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; margin-bottom: 6px;")
        layout.addWidget(hint)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Daily Backup")
        form.addRow("Name", self.name_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("What this task does")
        self.description_input.setMaximumHeight(70)
        form.addRow("Description", self.description_input)

        self.command_input = QComboBox()
        self.command_input.addItems(["script", "command"])
        form.addRow("Action", self.command_input)

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText(
            "script: /full/path/report_generator.py   |   command: df -h"
        )
        form.addRow("Target", self.target_input)

        self.schedule_input = QLineEdit()
        self.schedule_input.setPlaceholderText("manual")
        self.schedule_input.setText("manual")
        form.addRow("Schedule", self.schedule_input)

        self.enabled_input = QCheckBox("Enabled")
        self.enabled_input.setChecked(True)
        form.addRow("", self.enabled_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if task is not None:
            self._populate(task)

    def task(self) -> Task | None:
        return self._task

    def _populate(self, task: Task) -> None:
        self.name_input.setText(task.name)
        self.description_input.setPlainText(task.description or "")
        command = (task.command or "script").lower()
        index = self.command_input.findText(command)
        self.command_input.setCurrentIndex(index if index >= 0 else 0)
        self.target_input.setText(task.target or "")
        self.schedule_input.setText(task.schedule_as_string())
        self.enabled_input.setChecked(bool(task.enabled))

    def _accept(self) -> None:
        name = self.name_input.text().strip()
        target = self.target_input.text().strip()
        schedule = self.schedule_input.text().strip() or "manual"
        title = "Modify Task" if self._original is not None else "Create Task"

        if not name:
            QMessageBox.warning(self, title, "Name is required.")
            return
        if not target:
            QMessageBox.warning(self, title, "Target is required.")
            return

        try:
            if self._original is not None:
                # Keep id / history fields; update editable properties.
                self._original.modify(
                    name=name,
                    description=self.description_input.toPlainText().strip(),
                    enabled=self.enabled_input.isChecked(),
                    command=self.command_input.currentText(),
                    target=target,
                    schedule=schedule,
                )
                self._task = self._original
            else:
                self._task = Task(
                    name=name,
                    description=self.description_input.toPlainText().strip(),
                    enabled=self.enabled_input.isChecked(),
                    command=self.command_input.currentText(),
                    target=target,
                    string_schedule=schedule,
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Schedule", str(exc))
            return

        self.accept()


# Backwards-compatible alias
CreateTaskDialog = TaskEditorDialog
