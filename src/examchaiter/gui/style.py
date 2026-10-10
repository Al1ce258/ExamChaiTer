"""Windows 11 light theme QSS for the ExamChaiTer GUI (pure data, no IO)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

ACCENT = "#0078D4"
ACCENT_HOVER = "#106EBE"
ACCENT_PRESSED = "#005A9E"
SURFACE = "#F3F3F3"
CARD = "#FFFFFF"
BORDER = "#E1E1E1"

STYLE_QSS = """
* {
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
    color: #1B1B1B;
}
QMainWindow, QDialog {
    background-color: #F3F3F3;
}
QMainWindow::separator {
    width: 0px;
    height: 0px;
}
QWidget#centralWidget {
    background-color: #F3F3F3;
}
QFrame#card {
    background-color: #FFFFFF;
    border: 1px solid #E1E1E1;
    border-radius: 8px;
}
QLabel#cardTitle {
    font-size: 14px;
    font-weight: 600;
    color: #4B4B4B;
}
QLabel#answerLabel {
    font-size: 28pt;
    font-weight: 700;
    color: #0078D4;
}
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #E1E1E1;
    border-radius: 4px;
    padding: 6px 14px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #F5F5F5;
}
QPushButton:pressed {
    background-color: #EAEAEA;
}
QPushButton:disabled {
    color: #9A9A9A;
    background-color: #F7F7F7;
}
QPushButton#primaryButton {
    background-color: #0078D4;
    border: 1px solid #0078D4;
    color: #FFFFFF;
}
QPushButton#primaryButton:hover {
    background-color: #106EBE;
    border-color: #106EBE;
}
QPushButton#primaryButton:pressed {
    background-color: #005A9E;
    border-color: #005A9E;
}
QPushButton#primaryButton:disabled {
    background-color: #B7D8F0;
    border-color: #B7D8F0;
    color: #FFFFFF;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTableWidget, QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E1E1E1;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #0078D4;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {
    border: 2px solid #0078D4;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #8A8A8A;
    border-radius: 4px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #0078D4;
    border-color: #0078D4;
}
QStatusBar {
    background-color: #F3F3F3;
    border-top: 1px solid #E1E1E1;
    color: #4B4B4B;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #C8C8C8;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #A8A8A8;
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
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #C8C8C8;
    min-width: 24px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #A8A8A8;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QSplitter::handle {
    background: #E1E1E1;
}
QSplitter::handle:horizontal {
    width: 1px;
}
"""


def apply_style(app: QApplication) -> None:
    """Apply the Windows light stylesheet to ``app``."""
    app.setStyleSheet(STYLE_QSS)
