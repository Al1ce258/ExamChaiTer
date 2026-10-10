"""Main application window for ExamChaiTer."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from examchaiter.config import Settings
from examchaiter.gui.autopilot_bridge import AutoPilotBridge
from examchaiter.gui.state import GuiController
from examchaiter.gui.style import apply_style
from examchaiter.models import PipelineResult


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
        self.resize(900, 600)
        self.setMinimumSize(720, 480)

        instance = QApplication.instance()
        if instance is not None:
            apply_style(cast(QApplication, instance))

        self.bridge = AutoPilotBridge(self)
        controller.autopilot_callbacks = self.bridge.make_callbacks()

        self.window_combo = QComboBox()
        self.refresh_button = QPushButton("刷新")
        self.config_button = QPushButton("配置")
        self.history_button = QPushButton("历史")
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.window_combo, 1)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.config_button)
        toolbar.addWidget(self.history_button)

        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.answer_label = QLabel("—")
        self.answer_label.setObjectName("answerLabel")
        self.answer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        middle = QHBoxLayout()
        middle.addWidget(self._card("题目预览", self.preview_edit), 1)
        middle.addWidget(self._card("答案", self.answer_label), 1)

        self.answer_button = QPushButton("作答一次")
        self.answer_button.setObjectName("primaryButton")
        self.toggle_button = QPushButton("开始朗读")
        self.toggle_button.setObjectName("secondaryButton")
        self.auto_checkbox = QCheckBox("自动模式")
        self.quit_button = QPushButton("退出")
        bottom = QHBoxLayout()
        bottom.addWidget(self.answer_button)
        bottom.addWidget(self.toggle_button)
        bottom.addWidget(self.auto_checkbox)
        bottom.addStretch(1)
        bottom.addWidget(self.quit_button)

        central = QWidget()
        central.setObjectName("centralWidget")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addLayout(toolbar)
        layout.addLayout(middle, 1)
        layout.addLayout(bottom)
        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")

        self.refresh_button.clicked.connect(self.refresh_windows)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        self.answer_button.clicked.connect(self.on_answer_clicked)
        self.toggle_button.clicked.connect(self.on_toggle_tts_clicked)
        self.auto_checkbox.toggled.connect(self.on_auto_toggled)
        self.quit_button.clicked.connect(self.on_quit_clicked)
        self.bridge.state_changed.connect(self._on_auto_state)
        self.bridge.answer_ready.connect(self._on_answer_ready)
        self.bridge.status_message.connect(self._on_status_message)
        self.bridge.error_occurred.connect(self._on_error)

        self.refresh_windows()
        self._refresh_view()

    def _card(self, title: str, content: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(title_label)
        layout.addWidget(content, 1)
        return card

    def refresh_windows(self) -> None:
        self.window_combo.clear()
        for window in self.controller.list_windows():
            self.window_combo.addItem(f"{window.hwnd}: {window.title}", window.hwnd)

    def on_answer_clicked(self) -> None:
        QTimer.singleShot(0, self._run_answer)

    def _run_answer(self) -> None:
        self.controller.answer_once()
        self._refresh_view()

    def on_toggle_tts_clicked(self) -> None:
        self.controller.toggle_tts()
        self._refresh_view()

    def on_quit_clicked(self) -> None:
        self.controller.stop_tts()
        self.controller.stop_auto()
        self.hide()

    def _on_window_changed(self, index: int) -> None:
        hwnd = self.window_combo.itemData(index)
        if isinstance(hwnd, int):
            self.controller.pick_window(hwnd)

    def on_auto_toggled(self, checked: bool) -> None:
        if checked:
            hwnd = self.controller.state.current_hwnd
            if hwnd is None:
                self._set_auto_checked(False)
                return
            self.controller.start_auto(hwnd, "")
            if not self.controller.is_auto_running():
                self._set_auto_checked(False)
            return
        self.controller.stop_auto()

    def _on_auto_state(self, state_value: str) -> None:
        self._set_auto_checked(state_value == "running")
        self.statusBar().showMessage(f"自动模式：{state_value}")

    def _on_answer_ready(self, result: PipelineResult, from_cache: bool) -> None:
        self.preview_edit.setPlainText(result.question.text)
        self.answer_label.setText(result.answer.content)
        suffix = "（缓存）" if from_cache else ""
        self.statusBar().showMessage(f"已作答{suffix}")

    def _on_status_message(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_error(self, error: Exception) -> None:
        QMessageBox.warning(self, "ExamChaiTer 错误", str(error))

    def _set_auto_checked(self, checked: bool) -> None:
        self.auto_checkbox.blockSignals(True)
        self.auto_checkbox.setChecked(checked)
        self.auto_checkbox.blockSignals(False)

    def _refresh_view(self) -> None:
        state = self.controller.state
        self.preview_edit.setPlainText(state.last_question_text)
        self.answer_label.setText(state.last_answer.content if state.last_answer else "—")
        running = self.controller.is_tts_running()
        self.toggle_button.setText("停止朗读" if running else "开始朗读")
        self.toggle_button.setObjectName("primaryButton" if running else "secondaryButton")
        self._repolish(self.toggle_button)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.controller.stop_auto()
        event.ignore()
        self.hide()
