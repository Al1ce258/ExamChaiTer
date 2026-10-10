"""Injected capture -> OCR -> split -> LLM answer pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable
from io import BytesIO
from typing import Protocol

import numpy as np
from loguru import logger
from numpy.typing import NDArray
from PIL import Image

from examchaiter.capture.screenshot import dhash, hamming
from examchaiter.config import Settings
from examchaiter.llm.client import LLMClient, LLMFailed, LLMTimeout
from examchaiter.llm.prompts import build_messages, parse_answer
from examchaiter.llm.splitter import QuestionSplitter
from examchaiter.models import Answer, PipelineResult, Question, QuestionType, SplitQuestion
from examchaiter.ocr.engine import OcrEngine
from examchaiter.ocr.layout import blocks_to_text
from examchaiter.storage.hashing import question_hash
from examchaiter.storage.history_store import HistoryEntry, HistoryStore

ImageArray = NDArray[np.uint8]
WindowRect = tuple[int, int, int, int]


class Capture(Protocol):
    """Window capture operations injected into the pipeline."""

    def get_window_rect(self, hwnd: int) -> WindowRect: ...

    def is_window_alive(self, hwnd: int) -> bool: ...

    def focus_window(self, hwnd: int) -> bool: ...

    def grab_window(self, hwnd: int) -> ImageArray: ...


class ExamPipeline:
    """Run one injected capture/OCR/split/LLM answer cycle."""

    def __init__(
        self,
        capture: Capture,
        ocr: OcrEngine,
        llm: LLMClient,
        settings: Settings,
        splitter: QuestionSplitter,
        history_store: HistoryStore | None = None,
        session_id: str = "",
        _clock: Callable[[], float] | None = None,
        _sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.capture = capture
        self.ocr = ocr
        self.llm = llm
        self.settings = settings
        self.splitter = splitter
        self.history_store = history_store
        self.session_id = session_id
        self._clock = _clock or time.monotonic
        self._sleep = _sleep
        self._last_hash: int | None = None
        self._last_results: list[PipelineResult] = []

    def run_once(self, hwnd: int) -> list[PipelineResult]:
        """Run the pipeline once and return one result per split question."""

        started_at = self._clock()
        try:
            try:
                if not self.capture.is_window_alive(hwnd):
                    logger.warning("Target window is not alive: hwnd={}", hwnd)
                    return []
                self.capture.get_window_rect(hwnd)
            except Exception:
                logger.warning("Target window is unavailable: hwnd={}", hwnd)
                return []

            if not self.capture.focus_window(hwnd):
                logger.warning("Could not focus target window: hwnd={}", hwnd)
                return []

            self._sleep(self.settings.settle_ms / 1000.0)
            image = self.capture.grab_window(hwnd)
            image_hash = dhash(image)

            if (
                self._last_hash is not None
                and self._last_results
                and hamming(image_hash, self._last_hash) <= self.settings.dedup_threshold
            ):
                return [result.model_copy(update={"reused": True}) for result in self._last_results]

            blocks = self.ocr.recognize(image)
            raw_text = blocks_to_text(blocks)
            results = self._answer_text(raw_text, image, started_at)
            if not results:
                return []

            self._last_hash = image_hash
            self._last_results = results
            logger.trace("Pipeline completed in {:.1f} ms", (self._clock() - started_at) * 1000.0)
            return results
        except Exception:
            logger.exception("Pipeline failed for hwnd={}", hwnd)
            return []

    def _answer_text(
        self, raw_text: str, image: ImageArray, started_at: float
    ) -> list[PipelineResult]:
        if len(raw_text) >= self.settings.min_text_len:
            questions = self.splitter.split(raw_text)
            return [self._answer_question(question, started_at) for question in questions]

        if self.settings.llm_vision_model:
            image_bytes = _png_bytes(image)
            question = SplitQuestion(question_no="", text=raw_text)
            return [self._answer_question(question, started_at, images=[image_bytes])]

        return [
            PipelineResult(
                question=Question(text=raw_text),
                answer=Answer(qtype=QuestionType.UNKNOWN, content="未识别到文字"),
                reused=False,
            )
        ]

    def _answer_question(
        self,
        split_question: SplitQuestion,
        started_at: float,
        images: list[bytes] | None = None,
    ) -> PipelineResult:
        text = split_question.text
        qhash = question_hash(f"{split_question.question_no}|{text}")

        entry = self._find_cached(qhash)
        if entry is not None:
            return PipelineResult(
                question=Question(text=text),
                answer=Answer(qtype=_safe_qtype(entry.answer_qtype), content=entry.answer_content),
                reused=True,
                question_no=split_question.question_no,
            )

        question = Question(text=text, images=tuple(images or ()))
        messages = build_messages(text, images=images)
        try:
            raw = self.llm.complete(messages, json_mode=True)
        except (LLMFailed, LLMTimeout):
            logger.exception("LLM request failed")
            answer = Answer(qtype=QuestionType.UNKNOWN, content="⚠️ 请求失败")
        else:
            answer = parse_answer(raw)

        self._store_answer(split_question, qhash, answer, started_at)
        return PipelineResult(
            question=question,
            answer=answer,
            reused=False,
            question_no=split_question.question_no,
        )

    def _find_cached(self, qhash: str) -> HistoryEntry | None:
        if self.history_store is None or not self.session_id:
            return None
        try:
            return self.history_store.find_by_hash(self.session_id, qhash)
        except Exception:
            logger.warning("历史缓存查询失败，忽略缓存")
            return None

    def _store_answer(
        self,
        split_question: SplitQuestion,
        qhash: str,
        answer: Answer,
        started_at: float,
    ) -> None:
        if self.history_store is None or not self.session_id:
            return
        try:
            self.history_store.add_or_update_entry(
                self.session_id,
                HistoryEntry(
                    question_no=split_question.question_no,
                    question_hash=qhash,
                    question_text=split_question.text,
                    answer_qtype=answer.qtype.value,
                    answer_content=answer.content,
                    model=str(getattr(self.llm, "model", "")),
                    latency_ms=int((self._clock() - started_at) * 1000),
                    created_at=time.time(),
                ),
                flush_now=True,
            )
        except Exception:
            logger.exception("历史写入失败")


def _safe_qtype(value: str) -> QuestionType:
    try:
        return QuestionType(value)
    except ValueError:
        return QuestionType.UNKNOWN


def _png_bytes(image: ImageArray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()
