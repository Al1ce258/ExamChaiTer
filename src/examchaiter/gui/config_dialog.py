"""Configuration dialog that reads and writes ConfigStore via GuiController."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from examchaiter.gui.state import GuiController


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ConfigDialog(QDialog):
    """Edit the persisted :class:`AppConfig` and save it through the controller."""

    def __init__(self, controller: GuiController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("⚙ 配置")
        self.setMinimumWidth(460)

        self.base_url_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_toggle = QPushButton("显示")
        self.api_key_toggle.setCheckable(True)
        api_key_row = QHBoxLayout()
        api_key_row.setContentsMargins(0, 0, 0, 0)
        api_key_row.addWidget(self.api_key_edit, 1)
        api_key_row.addWidget(self.api_key_toggle)
        api_key_box = QWidget()
        api_key_box.setLayout(api_key_row)

        self.model_edit = QLineEdit()
        self.vision_edit = QLineEdit()
        self.tts_rate_spin = QSpinBox()
        self.tts_rate_spin.setRange(50, 400)
        self.poll_spin = QDoubleSpinBox()
        self.poll_spin.setRange(0.5, 10.0)
        self.poll_spin.setSingleStep(0.5)
        self.choice_spin = QSpinBox()
        self.choice_spin.setRange(1, 20)
        self.fill_short_spin = QSpinBox()
        self.fill_short_spin.setRange(1, 20)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(self._field_label("LLM Base URL"), self.base_url_edit)
        form.addRow(self._field_label("API Key"), api_key_box)
        form.addRow(self._field_label("模型名"), self.model_edit)
        form.addRow(self._field_label("Vision 模型"), self.vision_edit)
        form.addRow(self._field_label("TTS 语速"), self.tts_rate_spin)
        form.addRow(self._field_label("自动模式轮询间隔"), self.poll_spin)
        form.addRow(self._field_label("选择题朗读次数"), self.choice_spin)
        form.addRow(self._field_label("填空/简答朗读次数"), self.fill_short_spin)

        self.cancel_button = QPushButton("取消")
        self.save_button = QPushButton("保存")
        self.save_button.setProperty("class", "primary")
        buttons = QDialogButtonBox()
        buttons.addButton(self.cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.addButton(self.save_button, QDialogButtonBox.ButtonRole.AcceptRole)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.api_key_toggle.toggled.connect(self._on_toggle_api_key)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.save)

        self.load()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        label.setFixedWidth(140)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def load(self) -> None:
        config = self.controller.get_config()
        self.base_url_edit.setText(config.llm_base_url)
        self.api_key_edit.setText(config.llm_api_key)
        self.model_edit.setText(config.llm_model)
        self.vision_edit.setText(config.llm_vision_model)
        self.tts_rate_spin.setValue(_clamp(config.tts_rate, 50, 400))
        self.poll_spin.setValue(_clamp_float(config.auto_poll_interval, 0.5, 10.0))
        self.choice_spin.setValue(_clamp(config.auto_speak_choice_repeat, 1, 20))
        self.fill_short_spin.setValue(_clamp(config.auto_speak_fill_repeat, 1, 20))

    def save(self) -> None:
        config = self.controller.get_config()
        config.llm_base_url = self.base_url_edit.text().strip()
        config.llm_api_key = self.api_key_edit.text().strip()
        config.llm_model = self.model_edit.text().strip()
        config.llm_vision_model = self.vision_edit.text().strip()
        config.tts_rate = self.tts_rate_spin.value()
        config.auto_poll_interval = self.poll_spin.value()
        config.auto_speak_choice_repeat = self.choice_spin.value()
        config.auto_speak_fill_repeat = self.fill_short_spin.value()
        config.auto_speak_short_repeat = self.fill_short_spin.value()
        try:
            self.controller.save_config(config)
        except Exception as exc:
            QMessageBox.critical(self, "配置保存失败", str(exc))
            return
        self.accept()

    def _on_toggle_api_key(self, shown: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        self.api_key_edit.setEchoMode(mode)
        self.api_key_toggle.setText("隐藏" if shown else "显示")
