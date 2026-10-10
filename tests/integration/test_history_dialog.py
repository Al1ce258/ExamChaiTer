"""Integration tests for the history panel dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pytest_mock import MockerFixture

from examchaiter.gui.history_dialog import HistoryDialog
from examchaiter.storage.history_store import HistoryEntry, SessionMeta

pytestmark = pytest.mark.integration


def _entry(qhash: str = "h1", text: str = "question", no: str = "1") -> HistoryEntry:
    return HistoryEntry(
        question_no=no,
        question_hash=qhash,
        question_text=text,
        answer_qtype="choice",
        answer_content="B",
        created_at=1_700_000_000.0,
    )


def _controller(mocker: MockerFixture, entries: list[HistoryEntry] | None = None) -> object:
    controller = mocker.MagicMock()
    selected = entries if entries is not None else [_entry()]
    controller.list_sessions.return_value = [SessionMeta("s1", "Session 1", 1.0, len(selected))]
    controller.load_history.return_value = list(selected)
    controller.search_history.return_value = [("s1", entry) for entry in selected]
    controller.delete_session.return_value = True
    return controller


def test_dialog_lists_sessions_from_controller(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = HistoryDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.session_list.count() == 1


def test_selecting_session_loads_entries_into_table(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = HistoryDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.session_list.setCurrentRow(0)

    assert dialog.entry_table.rowCount() == 1


def test_search_filters_entries(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = HistoryDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.search_edit.setText("keyword")

    dialog.search_edit.returnPressed.emit()

    assert (
        controller.search_history.call_args.args[0],  # type: ignore[attr-defined]
        dialog.entry_table.rowCount(),
    ) == ("keyword", 1)


def test_delete_session_calls_controller_and_refreshes(
    qtbot: object, mocker: MockerFixture
) -> None:
    controller = _controller(mocker)
    dialog = HistoryDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.session_list.setCurrentRow(0)

    dialog.delete_selected_session()

    assert (
        controller.delete_session.call_args.args[0],  # type: ignore[attr-defined]
        controller.list_sessions.call_count,  # type: ignore[attr-defined]
    ) == ("s1", 2)


def test_table_has_question_no_column(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = HistoryDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    headers = [
        dialog.entry_table.horizontalHeaderItem(index).text()
        for index in range(dialog.entry_table.columnCount())
    ]

    assert ("题号" in headers, dialog.entry_table.columnWidth(1)) == (True, 60)


def test_entries_order_matches_json_order(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(
        mocker,
        [_entry("h1", no="1"), _entry("h2", no="2"), _entry("h3", no="3")],
    )
    dialog = HistoryDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.session_list.setCurrentRow(0)

    numbers = [
        dialog.entry_table.item(row, 1).text() for row in range(dialog.entry_table.rowCount())
    ]
    assert numbers == ["1", "2", "3"]
