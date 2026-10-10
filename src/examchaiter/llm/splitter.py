"""Rule-first question splitter with LLM fallback and single-question degrade."""

from __future__ import annotations

import re
from re import Match

from loguru import logger

from examchaiter.config import DEFAULT_SPLIT_PATTERNS, Settings
from examchaiter.llm.client import LLMClient, LLMFailed, LLMTimeout
from examchaiter.llm.prompts import build_split_messages, parse_split_response
from examchaiter.models import SplitQuestion


class QuestionSplitter:
    """Split raw OCR text into questions.

    Strategy: configured regexes first, then one LLM split call, and finally a
    single-question fallback. ``split`` never raises.
    """

    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self._llm = llm
        self._settings = settings
        self._last_mode = "fallback"

    @property
    def last_mode(self) -> str:
        return self._last_mode

    def split(self, raw_text: str) -> list[SplitQuestion]:
        try:
            text = raw_text if isinstance(raw_text, str) else ""
            if not text.strip():
                self._last_mode = "fallback"
                return []

            regex_questions = self._split_by_patterns(text)
            if regex_questions is not None:
                self._last_mode = "regex"
                return regex_questions

            llm_questions = self._split_with_llm(text)
            if llm_questions:
                self._last_mode = "llm"
                return llm_questions

            logger.warning("拆题失败，按整段单题处理")
            self._last_mode = "fallback"
            return [SplitQuestion(question_no="", text=text.strip())]
        except Exception:
            logger.exception("拆题异常，按整段单题处理")
            self._last_mode = "fallback"
            fallback = raw_text.strip() if isinstance(raw_text, str) else ""
            return [SplitQuestion(question_no="", text=fallback)]

    def _split_by_patterns(self, text: str) -> list[SplitQuestion] | None:
        compiled: list[re.Pattern[str]] = []
        for pattern in self._settings.split_patterns or []:
            try:
                compiled.append(re.compile(pattern, re.MULTILINE))
            except re.error:
                logger.warning("无效的拆题正则，已跳过: {}", pattern)

        if not compiled:
            return None

        lines = text.splitlines()
        start_index = next(
            (
                index
                for index, line in enumerate(lines[:5])
                if any(regex.search(line) for regex in compiled)
            ),
            None,
        )
        if start_index is None:
            return None
        if start_index > 0:
            text = "\n".join(lines[start_index:])

        allow_single = start_index > 0 or self._settings.split_patterns == DEFAULT_SPLIT_PATTERNS
        for regex in compiled:
            matches = list(regex.finditer(text))
            if not matches or (len(matches) < 2 and not allow_single):
                continue
            questions = self._segments(text, matches)
            short_count = sum(
                1 for question in questions if len(question.text) < self._settings.min_text_len
            )
            if short_count <= 1:
                return questions
        return None

    @staticmethod
    def _segments(text: str, matches: list[Match[str]]) -> list[SplitQuestion]:
        questions: list[SplitQuestion] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            raw_no = match.group(1) if match.groups() else ""
            question_no = "" if raw_no is None else str(raw_no).strip()
            questions.append(SplitQuestion(question_no=question_no, text=body))
        return questions

    def _split_with_llm(self, text: str) -> list[SplitQuestion]:
        try:
            raw = self._llm.complete(build_split_messages(text), json_mode=True)
        except (LLMFailed, LLMTimeout):
            logger.warning("拆题 LLM 调用失败，降级单题")
            return []
        except Exception:
            logger.exception("拆题 LLM 异常，降级单题")
            return []
        return self._normalize_llm_questions(parse_split_response(raw))

    @staticmethod
    def _normalize_llm_questions(questions: list[SplitQuestion]) -> list[SplitQuestion]:
        normalized: list[SplitQuestion] = []
        for question in questions:
            question_no = question.question_no.strip()
            text = question.text
            if not question_no:
                for pattern in DEFAULT_SPLIT_PATTERNS:
                    try:
                        match = re.match(pattern, text, flags=re.MULTILINE)
                    except re.error:
                        continue
                    if match is None or not match.groups():
                        continue
                    raw_no = match.group(1)
                    if raw_no is None:
                        continue
                    question_no = str(raw_no).strip()
                    text = text[match.end() :].lstrip()
                    break
            normalized.append(SplitQuestion(question_no=question_no, text=text))
        return normalized
