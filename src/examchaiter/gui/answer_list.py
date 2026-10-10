"""Reusable answer list widget that keeps per-question metadata."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QWidget

from examchaiter.gui.style import TEXT_DISABLED, TEXT_PRIMARY, TEXT_SECONDARY
from examchaiter.models import PipelineResult

_ITEM_FONT_PT = 20
_ROW_HEIGHT = 44
_PLACEHOLDER = "等待作答"


class AnswerList(QListWidget):
    """Show one row per answered question, preserving question numbers.

    Rows keep the full :class:`PipelineResult` metadata (question number, cache
    flag) instead of being flattened into a multi-line text block.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnswerList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWordWrap(True)
        self.set_results([])

    def set_results(self, results: list[PipelineResult]) -> None:
        """Replace every row with ``results``; an empty list shows the hint."""
        self.clear()
        if not results:
            self._add_row(_PLACEHOLDER, _PLACEHOLDER, disabled=True, color=TEXT_DISABLED)
            return
        for result in results:
            number = result.question_no or "?"
            plain = f"[{number}] {result.answer.content}"
            html = f'<span style="color:{TEXT_SECONDARY}">[{number}]</span> {result.answer.content}'
            if result.reused:
                plain += "  · 缓存"
                html += f'  <span style="color:{TEXT_DISABLED}">· 缓存</span>'
            self._add_row(plain, html)

    def row_texts(self) -> list[str]:
        """Plain text of every row (placeholder included)."""
        texts: list[str] = []
        for index in range(self.count()):
            item = self.item(index)
            texts.append(item.text() if item is not None else "")
        return texts

    def _add_row(
        self,
        plain: str,
        html: str,
        *,
        disabled: bool = False,
        color: str = TEXT_PRIMARY,
    ) -> None:
        item = QListWidgetItem(plain)
        item.setSizeHint(QSize(0, _ROW_HEIGHT))
        if disabled:
            item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.addItem(item)
        label = QLabel(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setStyleSheet(f"font-size: {_ITEM_FONT_PT}pt; color: {color};")
        self.setItemWidget(item, label)
