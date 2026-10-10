"""Unit tests for the AutoPilot state machine using fully faked dependencies."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from examchaiter.autopilot import (
    AutoPilot,
    AutoPilotCallbacks,
    AutoPilotConfig,
    AutoPilotState,
)
from examchaiter.llm.client import LLMFailed
from examchaiter.models import OcrBlock, QuestionType
from examchaiter.storage.history_store import HistoryEntry

_LONG_TEXT = "示例题目：1+1=? 请从下列选项中选择正确答案。"


class FakeCapture:
    """Return queued frame values, or raise queued exceptions."""

    def __init__(self, frames: list[Any]) -> None:
        self._frames = frames
        self.calls = 0

    def grab_window(self, _hwnd: int) -> Any:
        index = min(self.calls, len(self._frames) - 1)
        self.calls += 1
        frame = self._frames[index]
        if isinstance(frame, BaseException):
            raise frame
        return frame

    def dhash(self, image: Any) -> int:
        return int(image)


class BlockingCapture:
    """Block inside grab_window until the test releases it."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def grab_window(self, _hwnd: int) -> int:
        self.entered.set()
        self.release.wait(2.0)
        return 1

    def dhash(self, image: Any) -> int:
        return int(image)


@dataclass
class Recorder:
    """Capture AutoPilot callbacks for assertions."""

    states: list[AutoPilotState] = field(default_factory=list)
    answers: list[tuple[QuestionType, bool]] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)

    def callbacks(self) -> AutoPilotCallbacks:
        return AutoPilotCallbacks(
            on_state=self.states.append,
            on_answer=lambda result, from_cache: self.answers.append(
                (result.answer.qtype, from_cache)
            ),
            on_status=self.statuses.append,
            on_error=self.errors.append,
        )


class IterationDriver:
    """Injected sleep that stops the worker after a fixed number of iterations."""

    def __init__(self, iterations: int) -> None:
        self._iterations = iterations
        self.sleeps = 0
        self.done = threading.Event()
        self.autopilot: AutoPilot | None = None

    def sleep(self, _interval: float) -> None:
        self.sleeps += 1
        if self.sleeps >= self._iterations:
            assert self.autopilot is not None
            self.autopilot._stop_event.set()
            self.done.set()


def build(
    frames: list[Any] | None = None,
    *,
    capture: Any = None,
    iterations: int = 2,
    config: AutoPilotConfig | None = None,
    llm_responses: list[str] | None = None,
    history_entry: HistoryEntry | None = None,
) -> SimpleNamespace:
    capture = capture if capture is not None else FakeCapture(frames or [1, 1])
    ocr = MagicMock()
    ocr.recognize.return_value = [
        OcrBlock(text=_LONG_TEXT, bbox=(0.0, 0.0, 100.0, 10.0), confidence=0.99)
    ]
    llm = MagicMock()
    llm.model = "fake-model"
    llm.complete.side_effect = list(llm_responses or ['{"type":"choice","answer":"B"}'])
    loop_speaker = MagicMock()
    history = MagicMock()
    history.find_by_hash.return_value = history_entry
    recorder = Recorder()
    driver = IterationDriver(iterations)
    autopilot = AutoPilot(
        capture,
        ocr,
        llm,
        loop_speaker,
        history,
        "session-1",
        config or AutoPilotConfig(stable_frames=2, min_text_len=5),
        recorder.callbacks(),
        _sleep=driver.sleep,
    )
    driver.autopilot = autopilot
    return SimpleNamespace(
        capture=capture,
        ocr=ocr,
        llm=llm,
        loop_speaker=loop_speaker,
        history=history,
        recorder=recorder,
        driver=driver,
        autopilot=autopilot,
    )


def drive(deps: SimpleNamespace) -> None:
    deps.autopilot.start(0)
    assert deps.driver.done.wait(2.0) is True


def test_start_sets_running_state() -> None:
    capture = BlockingCapture()
    deps = build(capture=capture, iterations=1)
    deps.autopilot.start(0)
    assert capture.entered.wait(2.0) is True

    running = deps.autopilot.is_running()
    state = deps.autopilot.state
    deps.autopilot.start(0)
    still_running = deps.autopilot.is_running()
    capture.release.set()
    deps.autopilot.stop(timeout=1.0)

    assert (running, state, still_running) == (True, AutoPilotState.RUNNING, True)


def test_stable_frame_triggers_ocr_and_llm() -> None:
    deps = build([11, 11])
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        deps.ocr.recognize.call_count,
        deps.llm.complete.call_count,
        deps.recorder.answers,
    ) == (1, 1, [(QuestionType.CHOICE, False)])


def test_cache_hit_skips_llm() -> None:
    entry = HistoryEntry(
        question_hash="whatever",
        question_text=_LONG_TEXT,
        answer_qtype="choice",
        answer_content="C",
    )
    deps = build([7, 7], history_entry=entry)
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        deps.llm.complete.call_count,
        deps.recorder.answers,
        "缓存命中" in deps.recorder.statuses,
    ) == (0, [(QuestionType.CHOICE, True)], True)


def test_new_answer_writes_history_with_flush_now() -> None:
    deps = build([3, 3])
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        deps.history.add_or_update_entry.call_count,
        deps.history.add_or_update_entry.call_args.kwargs.get("flush_now"),
    ) == (1, True)


def test_dhash_change_resets_stable_count() -> None:
    deps = build([1, 2])
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert deps.ocr.recognize.call_count == 0


def test_same_stable_frame_answered_once() -> None:
    deps = build([5, 5, 5, 5], iterations=4)
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (deps.ocr.recognize.call_count, deps.recorder.answers) == (
        1,
        [(QuestionType.CHOICE, False)],
    )


@pytest.mark.parametrize(
    ("llm_response", "qtype", "expected_repeat", "expected_speech"),
    [
        ('{"type":"choice","answer":"B"}', QuestionType.CHOICE, 5, "答案是 B"),
        ('{"type":"fill","answer":"42"}', QuestionType.FILL, 3, "填空：42"),
        ('{"type":"short","answer":"因为"}', QuestionType.SHORT, 1, "因为"),
        ("", QuestionType.UNKNOWN, 1, "无法解析答案"),
    ],
)
def test_repeat_count_by_qtype(
    llm_response: str, qtype: QuestionType, expected_repeat: int, expected_speech: str
) -> None:
    deps = build([9, 9], llm_responses=[llm_response])
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        deps.loop_speaker.start.call_args.args[0],
        deps.loop_speaker.start.call_args.kwargs["max_repeats"],
        deps.recorder.answers,
    ) == (expected_speech, expected_repeat, [(qtype, False)])


def test_short_text_skipped() -> None:
    deps = build([1, 1], config=AutoPilotConfig(stable_frames=2, min_text_len=999))
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert deps.llm.complete.call_count == 0


def test_capture_error_calls_on_error_and_continues() -> None:
    deps = build([RuntimeError("grab failed"), 1, 1], iterations=3)
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (len(deps.recorder.errors), deps.llm.complete.call_count) == (1, 1)


def test_llm_error_calls_on_error_and_continues() -> None:
    deps = build([1, 1])
    deps.llm.complete.side_effect = LLMFailed("llm failed")
    drive(deps)
    state = deps.autopilot.state
    deps.autopilot.stop(timeout=1.0)

    assert (len(deps.recorder.errors), state) == (1, AutoPilotState.RUNNING)


def test_callback_exceptions_are_swallowed() -> None:
    recorder = Recorder()
    callbacks = recorder.callbacks()

    def _boom(_state: AutoPilotState) -> None:
        raise RuntimeError("callback failed")

    capture = FakeCapture([1, 1])
    ocr = MagicMock()
    ocr.recognize.return_value = [
        OcrBlock(text=_LONG_TEXT, bbox=(0.0, 0.0, 100.0, 10.0), confidence=0.99)
    ]
    llm = MagicMock()
    llm.complete.side_effect = ['{"type":"choice","answer":"B"}']
    driver = IterationDriver(2)
    autopilot = AutoPilot(
        capture,
        ocr,
        llm,
        MagicMock(),
        MagicMock(find_by_hash=MagicMock(return_value=None)),
        "session-1",
        AutoPilotConfig(stable_frames=2, min_text_len=5),
        AutoPilotCallbacks(
            on_state=_boom,
            on_answer=callbacks.on_answer,
            on_status=callbacks.on_status,
            on_error=callbacks.on_error,
        ),
        _sleep=driver.sleep,
    )
    driver.autopilot = autopilot
    autopilot.start(0)
    assert driver.done.wait(2.0) is True
    autopilot.stop(timeout=1.0)

    assert len(recorder.answers) == 1


def test_stop_exits_within_200ms() -> None:
    capture = FakeCapture([1, 1, 1])
    recorder = Recorder()
    autopilot = AutoPilot(
        capture,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        "session-1",
        AutoPilotConfig(poll_interval=5.0, stable_frames=99, min_text_len=5),
        recorder.callbacks(),
    )
    autopilot.start(0)

    started = time.monotonic()
    autopilot.stop(timeout=0.5)
    elapsed = time.monotonic() - started

    assert (autopilot.is_running(), autopilot.state, elapsed < 0.2) == (
        False,
        AutoPilotState.STOPPED,
        True,
    )


def test_stop_is_idempotent() -> None:
    deps = build([1, 1])
    drive(deps)

    deps.autopilot.stop(timeout=1.0)
    deps.autopilot.stop(timeout=1.0)
    deps.autopilot.stop(timeout=1.0)

    assert deps.autopilot.state is AutoPilotState.STOPPED
