"""Main application window for ExamChaiTer (Windows 11 light layout)."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
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
from examchaiter.gui.answer_list import AnswerList
from examchaiter.gui.autopilot_bridge import AutoPilotBridge
from examchaiter.gui.config_dialog import ConfigDialog
from examchaiter.gui.history_dialog import HistoryDialog
from examchaiter.gui.state import GuiController
from examchaiter.gui.style import apply_style
from examchaiter.models import PipelineResult

_STATUS_TEXT = {
    "idle": "就绪",
    "running": "自动模式运行中",
    "stopping": "正在停止…",
    "stopped": "自动模式已停止",
    "error": "错误",
}


def _add_shadow(widget: QWidget, blur: int, dy: int, alpha: int) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


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

        top_bar = self._build_top_bar()
        middle = self._build_cards()
        bottom_bar = self._build_bottom_bar()

        central = QWidget()
        central.setObjectName("centralWidget")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(top_bar)
        layout.addLayout(middle, 1)
        layout.addWidget(bottom_bar)
        self.setCentralWidget(central)
        self.statusBar().showMessage(self._format_status("idle"))

        self.refresh_button.clicked.connect(self.refresh_windows)
        self.window_combo.currentIndexChanged.connect(self._on_window_changed)
        self.answer_button.clicked.connect(self.on_answer_clicked)
        self.toggle_button.clicked.connect(self.on_toggle_tts_clicked)
        self.auto_checkbox.toggled.connect(self.on_auto_toggled)
        self.quit_button.clicked.connect(self.on_quit_clicked)
        self.config_button.clicked.connect(self.open_config_dialog)
        self.history_button.clicked.connect(self.open_history_dialog)
        self.bridge.state_changed.connect(self._on_auto_state)
        self.bridge.answer_ready.connect(self._on_answer_ready)
        self.bridge.round_done.connect(self._on_round_done)
        self.bridge.status_message.connect(self._on_status_message)
        self.bridge.error_occurred.connect(self._on_error)

        self.refresh_windows()
        self._refresh_view()

    def _build_top_bar(self) -> QFrame:
        self.window_combo = QComboBox()
        self.refresh_button = QPushButton("刷新")
        self.config_button = QPushButton("配置")
        self.history_button = QPushButton("历史")
        for button in (self.refresh_button, self.config_button, self.history_button):
            button.setProperty("class", "secondary")
            button.setMinimumWidth(80)
        search_icon = QLabel("🔍")
        search_icon.setObjectName("SearchIcon")

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(search_icon)
        layout.addWidget(self.window_combo, 1)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.config_button)
        layout.addWidget(self.history_button)
        _add_shadow(top_bar, blur=8, dy=1, alpha=25)
        return top_bar

    def _build_cards(self) -> QHBoxLayout:
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setObjectName("question_view")
        self.preview_edit.setReadOnly(True)
        self.answer_list = AnswerList()

        preview_card = self._card("题目预览", self.preview_edit)
        answer_card = self._card("答案", self.answer_list)
        _add_shadow(preview_card, blur=18, dy=2, alpha=22)
        _add_shadow(answer_card, blur=18, dy=2, alpha=22)

        middle = QHBoxLayout()
        middle.setSpacing(16)
        middle.addWidget(preview_card, 5)
        middle.addWidget(answer_card, 4)
        return middle

    def _build_bottom_bar(self) -> QFrame:
        self.answer_button = QPushButton("作答一次")
        self.answer_button.setProperty("class", "primary")
        self.toggle_button = QPushButton("开始朗读")
        self.toggle_button.setProperty("class", "secondary")
        self.auto_checkbox = QPushButton("自动模式")
        self.auto_checkbox.setCheckable(True)
        self.auto_checkbox.setProperty("class", "toggle")
        self.quit_button = QPushButton("退出")
        self.quit_button.setProperty("class", "danger")

        bottom_bar = QFrame()
        bottom_bar.setObjectName("BottomBar")
        layout = QHBoxLayout(bottom_bar)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(self.answer_button)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.auto_checkbox)
        layout.addStretch(1)
        layout.addWidget(self.quit_button)
        return bottom_bar

    def _card(self, title: str, content: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("CardFrame")
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
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
        results = list(self.controller.answer_once())
        self._refresh_view()
        if results:
            self.answer_list.set_results(results)
            cached = sum(1 for result in results if result.reused)
            self.statusBar().showMessage(f"共 {len(results)} 题，{cached} 题缓存命中")

    def on_toggle_tts_clicked(self) -> None:
        self.controller.toggle_tts()
        self._refresh_view()

    def on_quit_clicked(self) -> None:
        self.controller.stop_tts()
        self.controller.stop_auto()
        self.hide()

    def open_config_dialog(self) -> None:
        dialog = ConfigDialog(self.controller, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "配置", "配置已保存，重启后生效")

    def open_history_dialog(self) -> None:
        HistoryDialog(self.controller, self).exec()

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
        self.statusBar().showMessage(self._format_status(state_value))

    def _on_answer_ready(self, result: PipelineResult, from_cache: bool) -> None:
        number = result.question_no or "?"
        suffix = "（缓存）" if from_cache else ""
        self.statusBar().showMessage(f"已作答 [{number}]{suffix}")

    def _on_round_done(self, results: list[PipelineResult]) -> None:
        self.answer_list.set_results(list(results))
        if results:
            self.preview_edit.setPlainText(results[0].question.text)
        cached = sum(1 for result in results if result.reused)
        self.statusBar().showMessage(f"本轮共 {len(results)} 题，{cached} 题缓存命中")

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
        self.answer_list.set_results(list(state.last_results or []))
        running = self.controller.is_tts_running()
        self.toggle_button.setText("停止朗读" if running else "开始朗读")
        self.toggle_button.setProperty("class", "primary" if running else "secondary")
        self._repolish(self.toggle_button)

    @staticmethod
    def _format_status(state: str) -> str:
        return _STATUS_TEXT.get(state, state)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.controller.stop_auto()
        event.ignore()
        self.hide()
