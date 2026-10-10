"""Unit tests for the AutoPilot multi-question state machine with fake deps."""

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
from examchaiter.models import OcrBlock, PipelineResult, SplitQuestion
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
class FakeSplitter:
    questions: list[SplitQuestion] = field(
        default_factory=lambda: [SplitQuestion(question_no="", text=_LONG_TEXT)]
    )

    def split(self, _raw_text: str) -> list[SplitQuestion]:
        return list(self.questions)


@dataclass
class FakeHistory:
    entry: HistoryEntry | None = None
    added: list[HistoryEntry] = field(default_factory=list)
    flushes: list[bool] = field(default_factory=list)

    def find_by_hash(self, _session_id: str, _qhash: str) -> HistoryEntry | None:
        return self.entry

    def add_or_update_entry(
        self, _session_id: str, entry: HistoryEntry, *, flush_now: bool = False
    ) -> None:
        self.added.append(entry)
        self.flushes.append(flush_now)


@dataclass
class FakeLoopSpeaker:
    started: list[tuple[str, int | None]] = field(default_factory=list)
    stop_count: int = 0
    on_wait: Any = None

    def start(self, text: str, max_repeats: int | None = None) -> None:
        self.started.append((text, max_repeats))

    def stop(self) -> None:
        self.stop_count += 1

    def is_running(self) -> bool:
        return False

    def wait_done(self, timeout: float | None = None) -> bool:
        if self.on_wait is not None:
            self.on_wait()
        return True


class BlockingLoopSpeaker:
    """wait_done blocks until stop() releases it."""

    def __init__(self) -> None:
        self.started: list[tuple[str, int | None]] = []
        self.release = threading.Event()
        self.stop_count = 0

    def start(self, text: str, max_repeats: int | None = None) -> None:
        self.started.append((text, max_repeats))

    def stop(self) -> None:
        self.stop_count += 1
        self.release.set()

    def is_running(self) -> bool:
        return True

    def wait_done(self, timeout: float | None = None) -> bool:
        self.release.wait(timeout)
        return True


@dataclass
class Recorder:
    """Capture AutoPilot callbacks for assertions."""

    states: list[AutoPilotState] = field(default_factory=list)
    answers: list[tuple[str, bool]] = field(default_factory=list)
    rounds: list[list[PipelineResult]] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)

    def callbacks(self) -> AutoPilotCallbacks:
        return AutoPilotCallbacks(
            on_state=self.states.append,
            on_answer=lambda result, from_cache: self.answers.append(
                (result.question_no, from_cache)
            ),
            on_status=self.statuses.append,
            on_error=self.errors.append,
            on_round_done=self.rounds.append,
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
    splitter: Any = None,
    history: FakeHistory | None = None,
    loop_speaker: Any = None,
) -> SimpleNamespace:
    capture = capture if capture is not None else FakeCapture(frames or [1, 1])
    ocr = MagicMock()
    ocr.recognize.return_value = [
        OcrBlock(text=_LONG_TEXT, bbox=(0.0, 0.0, 100.0, 10.0), confidence=0.99)
    ]
    llm = MagicMock()
    llm.model = "fake-model"
    llm.complete.side_effect = list(llm_responses or ['{"type":"choice","answer":"B"}'])
    loop = loop_speaker if loop_speaker is not None else FakeLoopSpeaker()
    hist = history if history is not None else FakeHistory()
    recorder = Recorder()
    driver = IterationDriver(iterations)
    autopilot = AutoPilot(
        capture,
        ocr,
        llm,
        splitter or FakeSplitter(),
        loop,
        hist,
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
        loop=loop,
        history=hist,
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
    ) == (1, 1, [("", False)])


def test_cache_hit_skips_llm() -> None:
    entry = HistoryEntry(question_no="", answer_qtype="choice", answer_content="C")
    deps = build([7, 7], history=FakeHistory(entry=entry))
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        deps.llm.complete.call_count,
        deps.recorder.answers,
        "缓存命中" in deps.recorder.statuses,
    ) == (0, [("", True)], True)


def test_new_answer_writes_history_with_flush_now() -> None:
    splitter = FakeSplitter([SplitQuestion(question_no="2", text="新题内容")])
    deps = build([3, 3], splitter=splitter)
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        len(deps.history.added),
        deps.history.flushes,
        deps.history.added[0].question_no,
    ) == (1, [True], "2")


def test_dhash_change_resets_stable_count() -> None:
    deps = build([1, 2])
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert deps.ocr.recognize.call_count == 0


def test_same_stable_frame_answered_once() -> None:
    deps = build([5, 5, 5, 5], iterations=4)
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (deps.ocr.recognize.call_count, deps.recorder.answers) == (1, [("", False)])


def test_multi_question_round_reads_in_order() -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="1", text="第一题内容"),
            SplitQuestion(question_no="2", text="第二题内容"),
            SplitQuestion(question_no="3", text="第三题内容"),
        ]
    )
    llm_responses = [
        '{"type":"choice","answer":"A"}',
        '{"type":"multi_choice","answer":"ABD"}',
        '{"type":"fill","answer":"9"}',
    ]
    config = AutoPilotConfig(
        stable_frames=2,
        min_text_len=5,
        speak_choice_repeat=2,
        speak_multi_choice_repeat=3,
        speak_fill_repeat=1,
    )

    deps = build(
        [1, 1], iterations=2, splitter=splitter, llm_responses=llm_responses, config=config
    )
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (
        deps.recorder.answers,
        [repeat for _text, repeat in deps.loop.started],
        [text for text, _repeat in deps.loop.started],
    ) == (
        [("1", False), ("2", False), ("3", False)],
        [2, 3, 1],
        ["第 1 题，答案是 A", "第 2 题，答案是 A、B、D", "第 3 题，填空：9"],
    )


def test_multi_choice_uses_its_own_repeat() -> None:
    splitter = FakeSplitter([SplitQuestion(question_no="1", text="多选题内容")])
    config = AutoPilotConfig(
        stable_frames=2, min_text_len=5, speak_choice_repeat=5, speak_multi_choice_repeat=7
    )

    deps = build(
        [1, 1],
        iterations=2,
        splitter=splitter,
        llm_responses=['{"type":"multi_choice","answer":"ABD"}'],
        config=config,
    )
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert deps.loop.started == [("第 1 题，答案是 A、B、D", 7)]


def test_question_change_during_speaking_interrupts() -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="1", text="第一题内容"),
            SplitQuestion(question_no="2", text="第二题内容"),
        ]
    )
    deps = build([1, 1, 4095], iterations=3, splitter=splitter)
    deps.llm.complete.side_effect = [
        '{"type":"choice","answer":"B"}',
        '{"type":"choice","answer":"C"}',
    ]
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert len(deps.loop.started) == 1 and len(deps.recorder.rounds) == 1


def test_multi_question_round_tolerates_minor_frame_noise() -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="1", text="第一题内容"),
            SplitQuestion(question_no="2", text="第二题内容"),
        ]
    )
    deps = build([1, 1, 4, 1], iterations=3, splitter=splitter)
    deps.llm.complete.side_effect = [
        '{"type":"choice","answer":"B"}',
        '{"type":"choice","answer":"C"}',
    ]
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert [text for text, _repeat in deps.loop.started] == [
        "第 1 题，答案是 B",
        "第 2 题，答案是 C",
    ]


def test_no_number_question_gets_sequential_prefix() -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="", text="第一题内容"),
            SplitQuestion(question_no="", text="第二题内容"),
        ]
    )

    deps = build([1, 1], iterations=2, splitter=splitter)
    deps.llm.complete.side_effect = [
        '{"type":"choice","answer":"B"}',
        '{"type":"choice","answer":"B"}',
    ]
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert [text for text, _repeat in deps.loop.started] == [
        "第 1 题，答案是 B",
        "第 2 题，答案是 B",
    ]


def test_on_round_done_called_once_per_frame() -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="1", text="第一题内容"),
            SplitQuestion(question_no="2", text="第二题内容"),
            SplitQuestion(question_no="3", text="第三题内容"),
        ]
    )
    llm_responses = [
        '{"type":"choice","answer":"A"}',
        '{"type":"choice","answer":"B"}',
        '{"type":"choice","answer":"C"}',
    ]

    deps = build([1, 1], iterations=2, splitter=splitter, llm_responses=llm_responses)
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert (len(deps.recorder.answers), len(deps.recorder.rounds)) == (3, 1)


@pytest.mark.parametrize(
    ("llm_response", "expected_repeat", "expected_speech"),
    [
        ('{"type":"choice","answer":"B"}', 5, "第 1 题，答案是 B"),
        ('{"type":"multi_choice","answer":"ABD"}', 5, "第 1 题，答案是 A、B、D"),
        ('{"type":"fill","answer":"42"}', 3, "第 1 题，填空：42"),
        ('{"type":"short","answer":"因为"}', 1, "第 1 题，因为"),
        ("", 1, "第 1 题，无法解析答案"),
    ],
)
def test_repeat_count_by_qtype(
    llm_response: str, expected_repeat: int, expected_speech: str
) -> None:
    deps = build(
        [9, 9],
        iterations=2,
        splitter=FakeSplitter([SplitQuestion(question_no="1", text=_LONG_TEXT)]),
        llm_responses=[llm_response],
    )
    drive(deps)
    deps.autopilot.stop(timeout=1.0)

    assert deps.loop.started == [(expected_speech, expected_repeat)]


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
        FakeSplitter(),
        FakeLoopSpeaker(),
        FakeHistory(),
        "session-1",
        AutoPilotConfig(stable_frames=2, min_text_len=5),
        AutoPilotCallbacks(
            on_state=_boom,
            on_answer=callbacks.on_answer,
            on_status=callbacks.on_status,
            on_error=callbacks.on_error,
            on_round_done=callbacks.on_round_done,
        ),
        _sleep=driver.sleep,
    )
    driver.autopilot = autopilot
    autopilot.start(0)
    assert driver.done.wait(2.0) is True
    autopilot.stop(timeout=1.0)

    assert len(recorder.answers) == 1


def test_stop_exits_within_200ms() -> None:
    recorder = Recorder()
    autopilot = AutoPilot(
        FakeCapture([1, 1, 1]),
        MagicMock(),
        MagicMock(),
        FakeSplitter(),
        FakeLoopSpeaker(),
        FakeHistory(),
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


def test_stop_during_speaking_exits_within_200ms() -> None:
    splitter = FakeSplitter(
        [
            SplitQuestion(question_no="1", text="第一题内容"),
            SplitQuestion(question_no="2", text="第二题内容"),
        ]
    )
    loop = BlockingLoopSpeaker()
    deps = build([1, 1], splitter=splitter, loop_speaker=loop)
    deps.autopilot.start(0)
    deadline = time.monotonic() + 2.0
    while not loop.started and time.monotonic() < deadline:
        time.sleep(0.01)

    started = time.monotonic()
    deps.autopilot.stop(timeout=0.5)
    elapsed = time.monotonic() - started

    assert (deps.autopilot.is_running(), elapsed < 0.2) == (False, True)


def test_stop_is_idempotent() -> None:
    deps = build([1, 1])
    drive(deps)

    deps.autopilot.stop(timeout=1.0)
    deps.autopilot.stop(timeout=1.0)
    deps.autopilot.stop(timeout=1.0)

    assert deps.autopilot.state is AutoPilotState.STOPPED
