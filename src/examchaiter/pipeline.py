"""Injected capture -> OCR -> LLM answer pipeline."""

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
from examchaiter.models import Answer, PipelineResult, Question, QuestionType
from examchaiter.ocr.engine import OcrEngine
from examchaiter.ocr.layout import blocks_to_text

ImageArray = NDArray[np.uint8]
WindowRect = tuple[int, int, int, int]


class Capture(Protocol):
    """Window capture operations injected into the pipeline."""

    def get_window_rect(self, hwnd: int) -> WindowRect: ...

    def is_window_alive(self, hwnd: int) -> bool: ...

    def focus_window(self, hwnd: int) -> bool: ...

    def grab_window(self, hwnd: int) -> ImageArray: ...


class ExamPipeline:
    """Run one injected capture/OCR/LLM answer cycle."""

    def __init__(
        self,
        capture: Capture,
        ocr: OcrEngine,
        llm: LLMClient,
        settings: Settings,
        _clock: Callable[[], float] | None = None,
        _sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.capture = capture
        self.ocr = ocr
        self.llm = llm
        self.settings = settings
        self._clock = _clock or time.monotonic
        self._sleep = _sleep
        self._last_hash: int | None = None
        self._last_result: PipelineResult | None = None

    def run_once(self, hwnd: int) -> PipelineResult | None:
        """Run the pipeline once and absorb expected integration failures."""

        started_at = self._clock()
        try:
            try:
                if not self.capture.is_window_alive(hwnd):
                    logger.warning("Target window is not alive: hwnd={}", hwnd)
                    return None
                self.capture.get_window_rect(hwnd)
            except Exception:
                logger.warning("Target window is unavailable: hwnd={}", hwnd)
                return None

            if not self.capture.focus_window(hwnd):
                logger.warning("Could not focus target window: hwnd={}", hwnd)
                return None

            self._sleep(self.settings.settle_ms / 1000.0)
            image = self.capture.grab_window(hwnd)
            image_hash = dhash(image)

            if (
                self._last_hash is not None
                and self._last_result is not None
                and hamming(image_hash, self._last_hash) <= self.settings.dedup_threshold
            ):
                return PipelineResult(
                    question=self._last_result.question,
                    answer=self._last_result.answer,
                    reused=True,
                )

            blocks = self.ocr.recognize(image)
            question_text = blocks_to_text(blocks)

            if len(question_text) >= self.settings.min_text_len:
                question = Question(text=question_text)
                messages = build_messages(question_text)
            elif self.settings.llm_vision_model:
                image_bytes = _png_bytes(image)
                question = Question(text=question_text, images=(image_bytes,))
                messages = build_messages(question_text, images=[image_bytes])
            else:
                question = Question(text=question_text)
                return PipelineResult(
                    question=question,
                    answer=Answer(qtype=QuestionType.UNKNOWN, content="未识别到文字"),
                    reused=False,
                )

            try:
                raw = self.llm.complete(messages, json_mode=True)
            except (LLMFailed, LLMTimeout):
                logger.exception("LLM request failed")
                answer = Answer(qtype=QuestionType.UNKNOWN, content="⚠️ 请求失败")
            else:
                answer = parse_answer(raw)

            self._last_hash = image_hash
            result = PipelineResult(question=question, answer=answer, reused=False)
            self._last_result = result
            latency_ms = (self._clock() - started_at) * 1000.0
            logger.trace("Pipeline completed in {:.1f} ms", latency_ms)
            return result
        except Exception:
            logger.exception("Pipeline failed for hwnd={}", hwnd)
            return None


def _png_bytes(image: ImageArray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()
