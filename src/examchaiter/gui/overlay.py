"""Frameless draggable answer overlay."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from examchaiter.gui.state import GuiController


class OverlayWindow(QWidget):
    """Always-on-top answer overlay that only hides when closed."""

    def __init__(self, controller: GuiController) -> None:
        super().__init__(None)
        self.controller = controller
        self._drag_offset: QPoint | None = None
        self.setWindowTitle("ExamChaiTer Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.answer_label = QLabel("—")
        self.answer_label.setStyleSheet("font-size: 32px; font-weight: bold; color: white;")
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(28, 28)
        self.close_button.clicked.connect(self.hide)

        header = QHBoxLayout()
        header.addStretch(1)
        header.addWidget(self.close_button)
        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addWidget(self.answer_label)
        self.setLayout(layout)
        self.setStyleSheet("background-color: rgba(20, 20, 20, 220);")
        self.resize(360, 140)

    def show_answer(self) -> None:
        answer = self.controller.state.last_answer
        self.answer_label.setText(answer.content if answer is not None else "—")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
