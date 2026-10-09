"""Main application window for ExamChaiTer."""

from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from examchaiter.config import Settings
from examchaiter.gui.overlay import OverlayWindow
from examchaiter.gui.state import GuiController


class MainWindow(QMainWindow):
    """Thin Qt view over GuiController state and actions."""

    def __init__(
        self,
        controller: GuiController,
        settings: Settings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.settings = settings
        self.setWindowTitle("ExamChaiTer")

        self.window_combo = QComboBox()
        self.refresh_button = QPushButton("刷新")
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.answer_label = QLabel("—")
        self.answer_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.answer_button = QPushButton("作答一次")
        self.toggle_button = QPushButton("开始朗读")
        self.overlay_button = QPushButton("显示悬浮窗")
        self.quit_button = QPushButton("退出")

        top_row = QHBoxLayout()
        top_row.addWidget(self.window_combo, 1)
        top_row.addWidget(self.refresh_button)

        middle_row = QHBoxLayout()
        middle_row.addWidget(self.preview_edit, 2)
        middle_row.addWidget(self.answer_label, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.answer_button)
        bottom_row.addWidget(self.toggle_button)
        bottom_row.addWidget(self.overlay_button)
        bottom_row.addWidget(self.quit_button)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addLayout(middle_row, 1)
        layout.addLayout(bottom_row)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.overlay_window = OverlayWindow(controller)

        self.refresh_button.clicked.connect(self.refresh_windows)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        self.answer_button.clicked.connect(self.on_answer_clicked)
        self.toggle_button.clicked.connect(self.on_toggle_tts_clicked)
        self.overlay_button.clicked.connect(self._show_overlay)
        self.quit_button.clicked.connect(self.on_quit_clicked)

        self.refresh_windows()
        self._refresh_view()

    def refresh_windows(self) -> None:
        self.window_combo.clear()
        for window in self.controller.list_windows():
            self.window_combo.addItem(f"{window.hwnd}: {window.title}", window.hwnd)

    def on_answer_clicked(self) -> None:
        self.controller.answer_once()
        self._refresh_view()

    def on_toggle_tts_clicked(self) -> None:
        self.controller.toggle_tts()
        self._refresh_view()

    def on_quit_clicked(self) -> None:
        self.controller.stop_tts()
        self.hide()

    def _on_window_changed(self, index: int) -> None:
        hwnd = self.window_combo.itemData(index)
        if isinstance(hwnd, int):
            self.controller.pick_window(hwnd)

    def _show_overlay(self) -> None:
        self.overlay_window.show_answer()
        self.overlay_window.show()

    def _refresh_view(self) -> None:
        state = self.controller.state
        self.preview_edit.setPlainText(state.last_question_text)
        self.answer_label.setText(state.last_answer.content if state.last_answer else "—")
        self.toggle_button.setText("停止朗读" if self.controller.is_tts_running() else "开始朗读")
        self.overlay_window.show_answer()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
