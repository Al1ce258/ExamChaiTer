"""System tray integration for the main window."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from examchaiter.gui.main_window import MainWindow
from examchaiter.gui.state import GuiController


class TrayController(QObject):
    """Expose main-window actions through a system tray menu."""

    def __init__(
        self,
        app: QApplication,
        window: MainWindow,
        controller: GuiController,
    ) -> None:
        super().__init__(window)
        self.app = app
        self.window = window
        self.controller = controller
        self.tray = QSystemTrayIcon(
            window.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
            window,
        )
        self.tray.setToolTip("ExamChaiTer")

        menu = QMenu(window)
        show_action = QAction("显示主窗口", menu)
        answer_action = QAction("作答一次", menu)
        toggle_action = QAction("停/续朗读", menu)
        quit_action = QAction("退出", menu)
        menu.addAction(show_action)
        menu.addAction(answer_action)
        menu.addAction(toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        show_action.triggered.connect(self.window.show)
        answer_action.triggered.connect(self._answer)
        toggle_action.triggered.connect(self._toggle_tts)
        quit_action.triggered.connect(self._quit)
        self.tray.activated.connect(self._on_activated)
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _answer(self) -> None:
        self.controller.answer_once()
        self.window._refresh_view()

    def _toggle_tts(self) -> None:
        self.controller.toggle_tts()
        self.window._refresh_view()

    def _quit(self) -> None:
        self.controller.stop_tts()
        self.app.quit()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.window.show()
