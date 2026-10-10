"""Integration tests for the history panel dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from pytest_mock import MockerFixture

from examchaiter.gui.history_dialog import HistoryDialog
from examchaiter.storage.history_store import HistoryEntry, SessionMeta

pytestmark = pytest.mark.integration


def _entry(qhash: str = "h1", text: str = "question") -> HistoryEntry:
    return HistoryEntry(
        question_hash=qhash,
        question_text=text,
        answer_qtype="choice",
        answer_content="B",
        created_at=1_700_000_000.0,
    )


def _controller(mocker: MockerFixture, entry: HistoryEntry | None = None) -> object:
    controller = mocker.MagicMock()
    selected = entry or _entry()
    controller.list_sessions.return_value = [SessionMeta("s1", "Session 1", 1.0, 1)]
    controller.load_history.return_value = {"h1": selected}
    controller.search_history.return_value = [("s1", selected)]
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
