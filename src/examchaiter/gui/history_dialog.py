"""History panel: session list, cross-session search, and entry detail."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from examchaiter.gui.state import GuiController
from examchaiter.storage.history_store import HistoryEntry


def _format_time(timestamp: float) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


class HistoryDialog(QDialog):
    """Browse every stored session and search questions across sessions."""

    def __init__(self, controller: GuiController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("历史记录")
        self.resize(880, 560)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("跨 session 搜索题目")
        self.session_list = QListWidget()
        self.delete_button = QPushButton("删除选中 session")

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.search_edit)
        left_layout.addWidget(self.session_list, 1)
        left_layout.addWidget(self.delete_button)
        left = QWidget()
        left.setLayout(left_layout)

        self.entry_table = QTableWidget(0, 4)
        self.entry_table.setHorizontalHeaderLabels(["时间", "题型", "答案", "题目摘要"])
        self.entry_table.horizontalHeader().setStretchLastSection(True)
        self.entry_table.verticalHeader().setVisible(False)
        self.entry_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.entry_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setReadOnly(True)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.entry_table, 2)
        right_layout.addWidget(self.detail_edit, 1)
        right = QWidget()
        right.setLayout(right_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.close_button = QPushButton("关闭")
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(button_row)

        self.search_edit.returnPressed.connect(self.run_search)
        self.session_list.currentRowChanged.connect(self._on_session_changed)
        self.entry_table.itemSelectionChanged.connect(self._on_entry_selected)
        self.delete_button.clicked.connect(self.delete_selected_session)
        self.close_button.clicked.connect(self.accept)

        self._session_ids: list[str] = []
        self._entries: list[HistoryEntry] = []
        self.refresh_sessions()

    def refresh_sessions(self) -> None:
        self.session_list.clear()
        self._session_ids = []
        for meta in self.controller.list_sessions():
            self.session_list.addItem(meta.name or meta.session_id)
            self._session_ids.append(meta.session_id)

    def run_search(self) -> None:
        keyword = self.search_edit.text().strip()
        if not keyword:
            self._on_session_changed(self.session_list.currentRow())
            return
        self._populate_entries(list(self.controller.search_history(keyword)))

    def delete_selected_session(self) -> None:
        row = self.session_list.currentRow()
        if row < 0 or row >= len(self._session_ids):
            return
        self.controller.delete_session(self._session_ids[row])
        self.refresh_sessions()

    def _on_session_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._session_ids):
            return
        session_id = self._session_ids[row]
        entries = self.controller.load_history(session_id)
        self._populate_entries([(session_id, entry) for entry in entries.values()])

    def _on_entry_selected(self) -> None:
        rows = self.entry_table.selectionModel().selectedRows()
        if not rows:
            return
        index = rows[0].row()
        if 0 <= index < len(self._entries):
            self.detail_edit.setPlainText(self._entries[index].question_text)

    def _populate_entries(self, results: list[tuple[str, HistoryEntry]]) -> None:
        self._entries = [entry for _session_id, entry in results]
        self.entry_table.setRowCount(0)
        for session_id, entry in results:
            row = self.entry_table.rowCount()
            self.entry_table.insertRow(row)
            self.entry_table.setItem(row, 0, QTableWidgetItem(_format_time(entry.created_at)))
            self.entry_table.setItem(row, 1, QTableWidgetItem(entry.answer_qtype))
            self.entry_table.setItem(row, 2, QTableWidgetItem(entry.answer_content))
            summary = entry.question_text.replace("\n", " ")[:40]
            self.entry_table.setItem(row, 3, QTableWidgetItem(f"{session_id}: {summary}"))
        self.detail_edit.clear()
