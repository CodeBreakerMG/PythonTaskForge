# System tray icon — keep TaskForge running after the window is closed.

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_tray_icon() -> QIcon:
    """Simple generated icon so we do not need an assets file."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#1F6FEB"))
    painter.setPen(QColor("#0B3D91"))
    painter.drawRoundedRect(4, 4, size - 8, size - 8, 14, 14)
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(22)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), "TF")
    painter.end()
    return QIcon(pixmap)


class TaskForgeTray(QObject):
    """Menu-bar / system-tray controls for the background runtime."""

    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.icon = make_tray_icon()
        self.tray = QSystemTrayIcon(self.icon, parent)
        self.tray.setToolTip("TaskForge — running in background")

        menu = QMenu()
        open_action = QAction("Open Dashboard", menu)
        quit_action = QAction("Quit TaskForge", menu)
        open_action.triggered.connect(self.open_requested.emit)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.open_requested.emit()

    def show_message(self, title: str, body: str) -> None:
        self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 2500)
