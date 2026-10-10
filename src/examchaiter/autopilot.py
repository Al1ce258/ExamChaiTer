"""AutoPilot engine: watch a window, split questions, and read answers in order.

The engine is pure Python logic: every dependency is injected and the outside
world is notified through callbacks. It never imports Qt, win32gui, or pynput.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from loguru import logger

from examchaiter.llm.client import LLMClient
from examchaiter.llm.prompts import build_messages, parse_answer
from examchaiter.llm.splitter import QuestionSplitter
from examchaiter.models import Answer, PipelineResult, Question, QuestionType, SplitQuestion
from examchaiter.ocr.engine import OcrEngine
from examchaiter.ocr.layout import blocks_to_text
from examchaiter.output.formatter import to_speech_text
from examchaiter.storage.hashing import question_hash
from examchaiter.storage.history_store import HistoryEntry, HistoryStoreLike
from examchaiter.tts.speaker import LoopSpeaker


class AutoPilotCapture(Protocol):
    """Capture dependency: frame grabbing plus perceptual hashing."""

    def grab_window(self, hwnd: int) -> Any: ...

    def dhash(self, image: Any) -> int: ...


class AutoPilotState(str, Enum):  # noqa: UP042 - contract fixes (str, Enum) explicitly
    """Lifecycle of the AutoPilot worker thread."""

    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AutoPilotConfig:
    """Tunables for one AutoPilot run."""

    poll_interval: float = 1.5
    stable_frames: int = 2
    speak_choice_repeat: int = 5
    speak_multi_choice_repeat: int = 5
    speak_fill_repeat: int = 3
    speak_short_repeat: int = 1
    speak_interval: float = 3.0
    min_text_len: int = 20


def _noop_round(_results: list[PipelineResult]) -> None:
    return None


@dataclass
class AutoPilotCallbacks:
    """Callbacks used to report AutoPilot progress without owning a UI."""

    on_state: Callable[[AutoPilotState], None]
    on_answer: Callable[[PipelineResult, bool], None]
    on_status: Callable[[str], None]
    on_error: Callable[[Exception], None]
    on_round_done: Callable[[list[PipelineResult]], None] = _noop_round


class AutoPilot:
    """Poll a window and answer/speak once each time a new stable frame appears."""

    def __init__(
        self,
        capture: AutoPilotCapture,
        ocr: OcrEngine,
        llm: LLMClient,
        splitter: QuestionSplitter,
        loop_speaker: LoopSpeaker,
        history_store: HistoryStoreLike,
        session_id: str,
        config: AutoPilotConfig,
        callbacks: AutoPilotCallbacks,
        *,
        _sleep: Callable[[float], None] | None = None,
        _wait_done_timeout: float = 30.0,
    ) -> None:
        self._capture = capture
        self._ocr = ocr
        self._llm = llm
        self._splitter = splitter
        self._loop_speaker = loop_speaker
        self._history = history_store
        self._session_id = session_id
        self._config = config
        self._callbacks = callbacks
        self._sleep: Callable[[float], None] = _sleep if _sleep is not None else self._wait_interval
        self._wait_done_timeout = _wait_done_timeout
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._state = AutoPilotState.IDLE
        self._last_hash: int | None = None
        self._stable_count = 0
        self._has_answered = False

    @property
    def state(self) -> AutoPilotState:
        return self._state

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self, hwnd: int) -> None:
        """Start the worker thread. Non-blocking; ignored if already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._last_hash = None
            self._stable_count = 0
            self._has_answered = False
            self._thread = threading.Thread(
                target=self._run,
                args=(hwnd,),
                name="examchaiter-autopilot",
                daemon=True,
            )
            self._set_state(AutoPilotState.RUNNING)
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the worker, join it, and silence the speaker. Idempotent."""
        with self._lock:
            if self._state is AutoPilotState.RUNNING:
                self._set_state(AutoPilotState.STOPPING)
            self._stop_event.set()
            thread = self._thread
        self._loop_speaker.stop()
        if thread is not None:
            thread.join(timeout)
        with self._lock:
            self._thread = None
        self._loop_speaker.stop()
        self._set_state(AutoPilotState.STOPPED)

    def _run(self, hwnd: int) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick(hwnd)
            except Exception as exc:
                self._emit(self._callbacks.on_error, exc)
            self._sleep(self._config.poll_interval)

    def _tick(self, hwnd: int) -> None:
        image = self._capture.grab_window(hwnd)
        image_hash = self._capture.dhash(image)
        if image_hash == self._last_hash:
            self._stable_count += 1
        else:
            self._last_hash = image_hash
            self._stable_count = 1
            self._has_answered = False

        if self._stable_count < max(1, self._config.stable_frames) or self._has_answered:
            return

        text = blocks_to_text(self._ocr.recognize(image))
        if len(text) < self._config.min_text_len:
            self._emit(self._callbacks.on_status, "文本过短，跳过本轮")
            return

        questions = self._splitter.split(text)
        if not questions:
            self._emit(self._callbacks.on_status, "未拆出题目，跳过本轮")
            return

        results = self._answer_questions(questions)
        self._emit(self._callbacks.on_round_done, results)
        if self._speak_round(results, hwnd, image_hash):
            self._has_answered = True

    def _answer_questions(self, questions: list[SplitQuestion]) -> list[PipelineResult]:
        results: list[PipelineResult] = []
        for question in questions:
            result, from_cache = self._resolve_answer(question)
            results.append(result)
            self._emit(self._callbacks.on_answer, result, from_cache)
        return results

    def _resolve_answer(self, split_question: SplitQuestion) -> tuple[PipelineResult, bool]:
        text = split_question.text
        qhash = question_hash(f"{split_question.question_no}|{text}")
        entry = self._find_cached(qhash)
        if entry is not None:
            answer = Answer(qtype=_safe_qtype(entry.answer_qtype), content=entry.answer_content)
            from_cache = True
            self._emit(self._callbacks.on_status, "缓存命中")
        else:
            raw = self._llm.complete(build_messages(text), json_mode=True)
            answer = parse_answer(raw)
            from_cache = False
            self._store_answer(split_question, qhash, answer)
        result = PipelineResult(
            question=Question(text=text),
            answer=answer,
            reused=from_cache,
            question_no=split_question.question_no,
        )
        return result, from_cache

    def _find_cached(self, qhash: str) -> HistoryEntry | None:
        try:
            return self._history.find_by_hash(self._session_id, qhash)
        except Exception:
            logger.warning("历史缓存查询失败，忽略缓存")
            return None

    def _store_answer(self, split_question: SplitQuestion, qhash: str, answer: Answer) -> None:
        try:
            self._history.add_or_update_entry(
                self._session_id,
                HistoryEntry(
                    question_no=split_question.question_no,
                    question_hash=qhash,
                    question_text=split_question.text,
                    answer_qtype=answer.qtype.value,
                    answer_content=answer.content,
                    model=str(getattr(self._llm, "model", "")),
                    latency_ms=0,
                    created_at=time.time(),
                ),
                flush_now=True,
            )
        except Exception:
            logger.exception("历史写入失败")

    def _speak_round(self, results: list[PipelineResult], hwnd: int, frame_hash: int) -> bool:
        """Read ``results`` in order; ``False`` means interrupted before the end."""
        self._loop_speaker.stop()
        for index, result in enumerate(results):
            if self._stop_event.is_set():
                return False
            self._loop_speaker.start(
                self._speech_text(result, index),
                max_repeats=self._repeat_for(result.answer.qtype),
            )
            if not self._loop_speaker.wait_done(timeout=self._wait_done_timeout):
                return False
            if self._stop_event.is_set():
                return False
            if self._frame_changed(hwnd, frame_hash):
                self._loop_speaker.stop()
                return False
        return True

    def _frame_changed(self, hwnd: int, frame_hash: int) -> bool:
        try:
            return self._capture.dhash(self._capture.grab_window(hwnd)) != frame_hash
        except Exception:
            logger.warning("朗读期间帧检测失败，按已变化处理")
            return True

    def _speech_text(self, result: PipelineResult, index: int) -> str:
        body = to_speech_text(result.answer)
        if result.question_no:
            return body
        return f"第 {index + 1} 题，{body}"

    def _repeat_for(self, qtype: QuestionType) -> int:
        repeats = {
            QuestionType.CHOICE: self._config.speak_choice_repeat,
            QuestionType.MULTI_CHOICE: self._config.speak_multi_choice_repeat,
            QuestionType.FILL: self._config.speak_fill_repeat,
            QuestionType.SHORT: self._config.speak_short_repeat,
        }
        return repeats.get(qtype, 1)

    def _wait_interval(self, interval: float) -> None:
        self._stop_event.wait(interval)

    def _set_state(self, state: AutoPilotState) -> None:
        if self._state is state:
            return
        self._state = state
        self._emit(self._callbacks.on_state, state)

    @staticmethod
    def _emit(callback: Callable[..., None], *args: Any) -> None:
        try:
            callback(*args)
        except Exception:
            logger.exception("AutoPilot callback raised; ignored")


def _safe_qtype(value: str) -> QuestionType:
    try:
        return QuestionType(value)
    except ValueError:
        return QuestionType.UNKNOWN
