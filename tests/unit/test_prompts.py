"""Unit tests for prompt construction and answer parsing."""

import pytest

from examchaiter.llm.prompts import SYSTEM_PROMPT, build_messages, parse_answer
from examchaiter.models import QuestionType


@pytest.mark.parametrize(
    ("raw", "qtype", "content"),
    [
        ('{"type":"choice","answer":"B"}', QuestionType.CHOICE, "B"),
        ('```json\n{"type":"fill","answer":"42"}\n```', QuestionType.FILL, "42"),
        ('解释文字 {"type":"short","answer":"因为"}', QuestionType.SHORT, "因为"),
        ("答案：B", QuestionType.CHOICE, "B"),
        ("B", QuestionType.CHOICE, "B"),
        ("BC", QuestionType.SHORT, "BC"),
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
