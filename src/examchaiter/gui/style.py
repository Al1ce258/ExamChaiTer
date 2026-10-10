"""Windows 11 light theme palette and QSS for the ExamChaiTer GUI.

Pure data plus one tiny helper (``apply_style``); no IO, no business logic.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

# --- palette -----------------------------------------------------------------
BG_APP = "#F3F3F3"
BG_CARD = "#FFFFFF"
BG_INPUT = "#FBFBFB"
BG_HOVER = "#F5F5F5"
BORDER = "#E5E5E5"
BORDER_FOCUS = "#0078D4"
TEXT_PRIMARY = "#1F1F1F"
TEXT_SECONDARY = "#616161"
TEXT_DISABLED = "#A0A0A0"
PRIMARY = "#0078D4"
PRIMARY_HOVER = "#106EBE"
PRIMARY_PRESSED = "#005A9E"
DANGER = "#C42B1C"

PALETTE: dict[str, str] = {
    "bg_app": BG_APP,
    "bg_card": BG_CARD,
    "bg_input": BG_INPUT,
    "bg_hover": BG_HOVER,
    "border": BORDER,
    "border_focus": BORDER_FOCUS,
    "text_primary": TEXT_PRIMARY,
    "text_secondary": TEXT_SECONDARY,
    "text_disabled": TEXT_DISABLED,
    "primary": PRIMARY,
    "primary_hover": PRIMARY_HOVER,
    "primary_pressed": PRIMARY_PRESSED,
    "danger": DANGER,
}

_QSS_TEMPLATE = """
* {
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
    color: %(text_primary)s;
}
QMainWindow, QDialog {
    background-color: %(bg_app)s;
    border: none;
}
QWidget#centralWidget {
    background-color: %(bg_app)s;
}
QFrame#TopBar {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}
QFrame#BottomBar {
    background-color: %(bg_card)s;
    border: none;
    border-top: 1px solid %(border)s;
}
QFrame#CardFrame {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}
QLabel#CardTitle {
    font-size: 14pt;
    font-weight: 600;
    color: %(text_secondary)s;
    padding-bottom: 8px;
}
QLabel#SearchIcon {
    font-size: 14pt;
    padding: 0 4px;
}
QLabel#AnswerDisplay {
    font-size: 32pt;
    font-weight: 700;
    color: %(primary)s;
}
QLabel#AnswerDisplay[state="empty"] {
    font-size: 18pt;
    font-weight: 400;
    color: %(text_disabled)s;
}
QToolBar {
    background-color: %(bg_app)s;
    border: none;
}
QGroupBox {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    font-weight: 600;
    color: %(text_secondary)s;
}
QPushButton {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 6px 14px;
    min-height: 30px;
}
QPushButton:hover {
    background-color: %(bg_hover)s;
}
QPushButton:pressed {
    background-color: #EDEDED;
}
QPushButton:disabled {
    color: %(text_disabled)s;
    background-color: %(bg_hover)s;
    border-color: %(border)s;
}
QPushButton[class="primary"] {
    background-color: %(primary)s;
    border: none;
    color: #FFFFFF;
}
QPushButton[class="primary"]:hover {
    background-color: %(primary_hover)s;
}
QPushButton[class="primary"]:pressed {
    background-color: %(primary_pressed)s;
}
QPushButton[class="primary"]:disabled {
    background-color: #B7D8F0;
    color: #FFFFFF;
}
QPushButton[class="danger"] {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    color: %(danger)s;
}
QPushButton[class="danger"]:hover {
    background-color: #FDE7E9;
    border-color: %(danger)s;
}
QPushButton[class="toggle"] {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    color: %(text_secondary)s;
}
QPushButton[class="toggle"]:hover {
    background-color: %(bg_hover)s;
}
QPushButton[class="toggle"]:checked {
    background-color: %(primary)s;
    border-color: %(primary)s;
    color: #FFFFFF;
}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTableWidget, QListWidget {
    background-color: %(bg_input)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: %(primary)s;
    selection-color: #FFFFFF;
}
QComboBox {
    min-height: 32px;
}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {
    border: 2px solid %(border_focus)s;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid %(border)s;
}
QComboBox::down-arrow {
    width: 8px;
    height: 8px;
    background-color: %(text_secondary)s;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #8A8A8A;
    border-radius: 3px;
    background-color: %(bg_card)s;
}
QCheckBox::indicator:checked {
    background-color: %(primary)s;
    border-color: %(primary)s;
}
QStatusBar {
    background-color: %(bg_app)s;
    border-top: 1px solid %(border)s;
    color: %(text_secondary)s;
    padding: 6px 12px;
}
QHeaderView::section {
    background-color: %(bg_card)s;
    border: none;
    border-bottom: 1px solid %(border)s;
    padding: 4px 8px;
    font-weight: 600;
    color: %(text_secondary)s;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #C8C8C8;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #A0A0A0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #C8C8C8;
    min-width: 24px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #A0A0A0;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QSplitter::handle {
    background: %(border)s;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QToolTip {
    background-color: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 4px;
    color: %(text_primary)s;
    padding: 4px 6px;
}
"""

STYLE_QSS = _QSS_TEMPLATE % PALETTE


def apply_style(app: QApplication) -> None:
    """Apply the Windows light stylesheet to ``app``."""
    app.setStyleSheet(STYLE_QSS)
