"""Unit tests for the rule-first question splitter."""

from __future__ import annotations

from typing import Any

from examchaiter.config import Settings
from examchaiter.llm.client import FakeLLMClient, LLMTimeout
from examchaiter.llm.splitter import QuestionSplitter
from examchaiter.models import SplitQuestion

_NUMBERED = "1. 第一题内容甲乙丙\n2. 第二题内容甲乙丙\n3. 第三题内容甲乙丙\n4. 第四题内容甲乙丙"


class TimeoutLLM:
    def complete(self, _messages: list[dict[str, object]], *, json_mode: bool = False) -> str:
        raise LLMTimeout("timed out")


class BrokenLLM:
    def complete(self, _messages: list[dict[str, object]], *, json_mode: bool = False) -> str:
        raise RuntimeError("llm boom")


def _splitter(llm: Any = None, **overrides: Any) -> QuestionSplitter:
    settings = Settings(_env_file=None, **overrides)
    return QuestionSplitter(llm or FakeLLMClient(responses=[]), settings)


def test_split_with_numbered_lines_returns_questions() -> None:
    questions = _splitter().split(_NUMBERED)

    assert [(question.question_no, question.text) for question in questions] == [
        ("1", "第一题内容甲乙丙"),
        ("2", "第二题内容甲乙丙"),
        ("3", "第三题内容甲乙丙"),
        ("4", "第四题内容甲乙丙"),
    ]


def test_split_with_custom_pattern_works() -> None:
    splitter = _splitter(split_patterns=[r"^Q\d+\.\s*"])

    questions = splitter.split("Q1. 甲题内容说明\nQ2. 乙题内容说明")

    assert [question.text for question in questions] == ["甲题内容说明", "乙题内容说明"]


def test_split_without_numbering_uses_llm() -> None:
    llm = FakeLLMClient(responses=['[{"no": "1", "text": "甲"}, {"no": "2", "text": "乙"}]'])

    questions = _splitter(llm).split("没有编号的一整段文本")

    assert questions == [
        SplitQuestion(question_no="1", text="甲"),
        SplitQuestion(question_no="2", text="乙"),
    ]


def test_split_with_malformed_llm_response_degrades_to_single() -> None:
    llm = FakeLLMClient(responses=["not json"])

    questions = _splitter(llm).split("一整段没有编号的题目")

    assert questions == [SplitQuestion(question_no="", text="一整段没有编号的题目")]


def test_split_with_empty_llm_array_degrades_to_single() -> None:
    llm = FakeLLMClient(responses=["[]"])

    questions = _splitter(llm).split("单题没有题号")

    assert questions == [SplitQuestion(question_no="", text="单题没有题号")]


def test_split_with_llm_timeout_degrades_to_single() -> None:
    questions = _splitter(TimeoutLLM()).split("一整段没有编号的题目")

    assert questions == [SplitQuestion(question_no="", text="一整段没有编号的题目")]


def test_split_with_llm_exception_degrades_to_single() -> None:
    questions = _splitter(BrokenLLM()).split("没有编号的题目")

    assert questions == [SplitQuestion(question_no="", text="没有编号的题目")]


def test_split_with_empty_text_returns_empty_list() -> None:
    assert _splitter().split("   \n ") == []


def test_split_with_too_many_short_segments_uses_llm() -> None:
    llm = FakeLLMClient(responses=['[{"no": "1", "text": "合并后的题目内容"}]'])

    questions = _splitter(llm).split("1. a\n2. b")

    assert questions == [SplitQuestion(question_no="1", text="合并后的题目内容")]


def test_split_skips_invalid_regex_patterns() -> None:
    llm = FakeLLMClient(responses=['[{"no": "", "text": "甲"}]'])
    splitter = _splitter(llm, split_patterns=["([", r"^(\d+)\.\s*"])

    questions = splitter.split("1. 甲题内容")

    assert questions == [SplitQuestion(question_no="", text="甲")]


def test_split_swallows_unexpected_errors() -> None:
    class BoomSettings:
        @property
        def split_patterns(self) -> list[str]:
            raise RuntimeError("boom")

    splitter = QuestionSplitter(FakeLLMClient(responses=[]), BoomSettings())  # type: ignore[arg-type]

    assert splitter.split("text") == [SplitQuestion(question_no="", text="text")]


def test_split_patterns_supports_cjk_brackets() -> None:
    questions = _splitter().split("【1】甲题内容甲乙\n【2】乙题内容甲乙")

    assert [(q.question_no, q.text) for q in questions] == [
        ("1", "甲题内容甲乙"),
        ("2", "乙题内容甲乙"),
    ]


def test_split_patterns_supports_timu_prefix() -> None:
    questions = _splitter().split("题目1：甲题内容甲乙\n题目2：乙题内容甲乙")

    assert [q.question_no for q in questions] == ["1", "2"]


def test_split_patterns_supports_cjk_numbered_list() -> None:
    questions = _splitter().split("一、甲题内容甲乙\n二、乙题内容甲乙")

    assert [q.text for q in questions] == ["甲题内容甲乙", "乙题内容甲乙"]


def test_last_mode_regex_when_pattern_matches() -> None:
    splitter = _splitter()

    splitter.split(_NUMBERED)

    assert splitter.last_mode == "regex"


def test_last_mode_llm_when_regex_fails() -> None:
    llm = FakeLLMClient(responses=['[{"no": "1", "text": "甲"}]'])
    splitter = _splitter(llm)

    splitter.split("没有编号的一整段文本")

    assert splitter.last_mode == "llm"


def test_last_mode_fallback_when_both_fail() -> None:
    llm = FakeLLMClient(responses=["not json"])
    splitter = _splitter(llm)

    splitter.split("没有编号的一整段文本")

    assert splitter.last_mode == "fallback"


def test_skips_leading_noise_before_numbered_question() -> None:
    splitter = _splitter()

    questions = splitter.split("language.ini\n文件 编辑\n1. 题目内容\nA. 选项")

    assert len(questions) == 1 and questions[0].question_no == "1"


def test_no_number_within_first_5_lines_falls_back_to_llm() -> None:
    llm = FakeLLMClient(responses=['[{"no": "9", "text": "LLM题"}]'])
    splitter = _splitter(llm)
    text = "噪音一\n噪音二\n噪音三\n噪音四\n噪音五\n1. 题目内容"

    questions = splitter.split(text)

    assert [(q.question_no, q.text) for q in questions] == [("9", "LLM题")]


def test_llm_result_with_empty_no_extracts_number_from_text() -> None:
    llm = FakeLLMClient(responses=['[{"no": "", "text": "1. 题目内容"}]'])
    splitter = _splitter(llm)

    questions = splitter.split("没有编号的一整段文本")

    assert [(q.question_no, q.text) for q in questions] == [("1", "题目内容")]


def test_llm_result_keeps_explicit_no() -> None:
    llm = FakeLLMClient(responses=['[{"no": "2", "text": "题目内容"}]'])
    splitter = _splitter(llm)

    questions = splitter.split("没有编号的一整段文本")

    assert [(q.question_no, q.text) for q in questions] == [("2", "题目内容")]


def test_question_text_has_no_prefix_after_extraction() -> None:
    llm = FakeLLMClient(responses=['[{"no": "", "text": "1. 题目内容"}]'])
    splitter = _splitter(llm)

    questions = splitter.split("没有编号的一整段文本")

    assert questions[0].text == "题目内容"
