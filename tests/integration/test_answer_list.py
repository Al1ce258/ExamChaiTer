"""Integration tests for the reusable answer list widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt

from examchaiter.gui.answer_list import AnswerList
from examchaiter.models import Answer, PipelineResult, Question, QuestionType

pytestmark = pytest.mark.integration


def _result(no: str = "1", content: str = "B", *, reused: bool = False) -> PipelineResult:
    return PipelineResult(
        question=Question(text="question"),
        answer=Answer(qtype=QuestionType.CHOICE, content=content),
        reused=reused,
        question_no=no,
    )


def test_empty_shows_placeholder(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    assert view.row_texts() == ["等待作答"]


def test_single_result_shows_one_item_with_number(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result(no="1", content="B")])

    assert (view.count(), view.row_texts()[0]) == (1, "[1] B")


def test_multi_results_order_matches_input(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result("1", "A"), _result("2", "B"), _result("3", "C")])

    assert view.row_texts() == ["[1] A", "[2] B", "[3] C"]


def test_reused_result_appends_cache_hint(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result("1", "B", reused=True)])

    assert view.row_texts()[0].endswith("· 缓存")


def test_no_number_result_shows_question_mark(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result(no="", content="B")])

    assert view.row_texts()[0].startswith("[?]")


def test_placeholder_row_is_disabled(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    item = view.item(0)

    assert item is not None and item.flags() == Qt.ItemFlag.NoItemFlags


def test_set_results_replaces_not_appends(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result("1", "A"), _result("2", "B"), _result("3", "C")])
    view.set_results([_result("9", "D")])

    assert (view.count(), view.row_texts()) == (1, ["[9] D"])


def test_empty_then_results_no_ghost_items(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result("1", "A"), _result("2", "B")])
    view.set_results([])
    view.set_results([_result("3", "C")])

    assert (view.count(), view.row_texts()) == (1, ["[3] C"])


def test_items_do_not_carry_duplicate_display_text(qtbot: object) -> None:
    view = AnswerList()
    qtbot.addWidget(view)  # type: ignore[attr-defined]

    view.set_results([_result("1", "B")])

    item = view.item(0)
    assert item is not None and item.text() == ""
    assert view.row_texts() == ["[1] B"]
