# Settings dialog — configure where the SQLite database lives.

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from config.settings import AppSettings, load_settings, settings_path
from database.database import get_db_path


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self._settings = load_settings()
        self._changed_db_path: str | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Choose where TaskForge stores tasks, history, and logs.\n"
            f"App settings file: {settings_path()}"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(intro)

        try:
            current = str(get_db_path())
        except RuntimeError:
            current = self._settings.db_path

        form = QFormLayout()
        path_row = QHBoxLayout()
        self.db_path_input = QLineEdit(current)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.db_path_input, stretch=1)
        path_row.addWidget(browse_btn)
        form.addRow("Database file", path_row)
        layout.addLayout(form)

        note = QLabel(
            "If you pick a new file, TaskForge will create it (or open it if it exists). "
            "Your previous database is left untouched."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; margin-top: 6px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_db_path(self) -> str | None:
        return self._changed_db_path

    def _browse(self) -> None:
        start = self.db_path_input.text().strip() or str(Path.home())
        start_path = Path(start)
        directory = str(start_path.parent if start_path.suffix else start_path)
        chosen, _ = QFileDialog.getSaveFileName(
            self,
            "Select database file",
            str(start_path if start_path.suffix else Path(directory) / "taskforge.db"),
            "SQLite Database (*.db);;All Files (*)",
        )
        if chosen:
            self.db_path_input.setText(chosen)

    def _save(self) -> None:
        raw = self.db_path_input.text().strip()
        if not raw:
            QMessageBox.warning(self, "Settings", "Database path is required.")
            return

        path = Path(raw).expanduser()
        if path.exists() and path.is_dir():
            QMessageBox.warning(
                self,
                "Settings",
                "Please choose a .db file path, not a folder.",
            )
            return

        if path.suffix.lower() != ".db":
            path = path.with_suffix(".db")
            self.db_path_input.setText(str(path))

        self._settings = AppSettings(db_path=str(path))
        self._changed_db_path = str(path)
        self.accept()
