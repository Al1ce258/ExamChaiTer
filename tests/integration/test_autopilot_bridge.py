"""Integration tests for the AutoPilot -> Qt signal bridge."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from examchaiter.autopilot import AutoPilotState
from examchaiter.gui.autopilot_bridge import AutoPilotBridge
from examchaiter.models import Answer, PipelineResult, Question, QuestionType

pytestmark = pytest.mark.integration


def test_make_callbacks_returns_four_callables(qtbot: object) -> None:
    bridge = AutoPilotBridge()

    callbacks = bridge.make_callbacks()

    assert all(
        callable(handler)
        for handler in (
            callbacks.on_state,
            callbacks.on_answer,
            callbacks.on_status,
            callbacks.on_error,
        )
    )


def test_on_state_emits_state_changed(qtbot: object) -> None:
    bridge = AutoPilotBridge()
    callbacks = bridge.make_callbacks()

    with qtbot.waitSignal(bridge.state_changed, timeout=1000) as blocker:  # type: ignore[attr-defined]
        callbacks.on_state(AutoPilotState.RUNNING)

    assert blocker.args == ["running"]


def test_on_answer_emits_with_from_cache_flag(qtbot: object) -> None:
    bridge = AutoPilotBridge()
    callbacks = bridge.make_callbacks()
    result = PipelineResult(
        question=Question(text="question"),
        answer=Answer(qtype=QuestionType.CHOICE, content="B"),
    )

    with qtbot.waitSignal(bridge.answer_ready, timeout=1000) as blocker:  # type: ignore[attr-defined]
        callbacks.on_answer(result, True)

    assert (blocker.args[0], blocker.args[1]) == (result, True)


def test_on_status_emits_message(qtbot: object) -> None:
    bridge = AutoPilotBridge()
    callbacks = bridge.make_callbacks()

    with qtbot.waitSignal(bridge.status_message, timeout=1000) as blocker:  # type: ignore[attr-defined]
        callbacks.on_status("缓存命中")

    assert blocker.args == ["缓存命中"]


def test_on_error_emits_exception(qtbot: object) -> None:
    bridge = AutoPilotBridge()
    callbacks = bridge.make_callbacks()
    error = RuntimeError("bridge boom")

    with qtbot.waitSignal(bridge.error_occurred, timeout=1000) as blocker:  # type: ignore[attr-defined]
        callbacks.on_error(error)

    assert blocker.args == [error]
