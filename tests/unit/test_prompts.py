"""Unit tests for prompt construction and answer parsing."""

import pytest

from examchaiter.llm.prompts import (
    SPLIT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_messages,
    build_split_messages,
    parse_answer,
    parse_split_response,
)
from examchaiter.models import QuestionType, SplitQuestion


@pytest.mark.parametrize(
    ("raw", "qtype", "content"),
    [
        ('{"type":"choice","answer":"B"}', QuestionType.CHOICE, "B"),
        ('```json\n{"type":"fill","answer":"42"}\n```', QuestionType.FILL, "42"),
        ('解释文字 {"type":"short","answer":"因为"}', QuestionType.SHORT, "因为"),
        ("答案：B", QuestionType.CHOICE, "B"),
        ("B", QuestionType.CHOICE, "B"),
        ("BC", QuestionType.MULTI_CHOICE, "B C"),
        ('{"type":"multi_choice","answer":"ABD"}', QuestionType.MULTI_CHOICE, "A B D"),
        ("填空 ____", QuestionType.FILL, "填空"),
        ("这是一段简答。", QuestionType.SHORT, "这是一段简答。"),
        ("", QuestionType.UNKNOWN, ""),
        ("@@@###", QuestionType.SHORT, "@@@###"),
        ('{"type":"choice"}', QuestionType.SHORT, '{"type":"choice"}'),
        ('{"type":"other","answer":"B"}', QuestionType.SHORT, '{"type":"other","answer":"B"}'),
        ("第一行\n第二行\n第三行", QuestionType.SHORT, "第一行\n第二行\n第三行"),
    ],
)
def test_parse_answer_with_supported_input_returns_expected(
    raw: str, qtype: QuestionType, content: str
) -> None:
    answer = parse_answer(raw)

    assert (answer.qtype, answer.content) == (qtype, content)


def test_parse_answer_with_none_returns_unknown_empty() -> None:
    answer = parse_answer(None)  # type: ignore[arg-type]

    assert (answer.qtype, answer.content) == (QuestionType.UNKNOWN, "")


def test_build_messages_without_images_returns_system_and_user() -> None:
    assert len(build_messages("1+1=?")) == 2


def test_build_messages_with_images_contains_image_url() -> None:
    messages = build_messages("Describe", images=[b"png"])

    assert "image_url" in str(messages[1])


def test_build_messages_system_prompt_requires_json_only() -> None:
    assert "只输出 JSON" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    ("raw", "content"),
    [
        ("ABD", "A B D"),
        ("A,B,D", "A B D"),
        ("答案：AB", "A B"),
        ("ABCD", "A B C D"),
        ("A B", "A B"),
        ("AB C", "A B C"),
        ("答案:ABD", "A B D"),
    ],
)
def test_parse_answer_multi_choice_normalizes_letters(raw: str, content: str) -> None:
    answer = parse_answer(raw)

    assert (answer.qtype, answer.content) == (QuestionType.MULTI_CHOICE, content)


def test_build_split_messages_returns_system_and_user() -> None:
    messages = build_split_messages("1. a\n2. b")

    assert len(messages) == 2 and "JSON 数组" in SPLIT_SYSTEM_PROMPT


def test_parse_split_response_with_valid_array_returns_questions() -> None:
    raw = '[{"no": "1", "text": "甲"}, {"no": "", "text": "乙"}]'

    assert parse_split_response(raw) == [
        SplitQuestion(question_no="1", text="甲"),
        SplitQuestion(question_no="", text="乙"),
    ]


def test_parse_split_response_with_malformed_input_returns_empty() -> None:
    assert parse_split_response("not json") == []


def test_parse_split_response_extracts_array_from_prose() -> None:
    raw = '结果如下：[{"no": "2", "text": "乙题"}]'

    assert parse_split_response(raw) == [SplitQuestion(question_no="2", text="乙题")]
