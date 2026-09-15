# Settings dialog — configure where the SQLite database lives.

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
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

from config.settings import AppSettings, load_settings, save_settings, settings_path
from database.database import get_db_path


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self._settings = load_settings()
        self._saved_settings: AppSettings | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Configure TaskForge behavior and storage.\n"
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

        self.keep_running_checkbox = QCheckBox(
            "Keep running in the menu bar when I close the window"
        )
        self.keep_running_checkbox.setChecked(self._settings.keep_running_in_tray)
        self.keep_running_checkbox.setToolTip(
            "When on, closing the window hides TaskForge to the menu bar and macOS can "
            "restart it after unexpected crashes. Quit from the tray menu to exit fully."
        )
        layout.addWidget(self.keep_running_checkbox)

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

    def saved_settings(self) -> AppSettings | None:
        return self._saved_settings

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

        self._settings = AppSettings(
            db_path=str(path),
            keep_running_in_tray=self.keep_running_checkbox.isChecked(),
        )
        save_settings(self._settings)
        self._saved_settings = self._settings
        self.accept()
