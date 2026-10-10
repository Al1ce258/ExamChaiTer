"""Unit tests for pure answer formatting."""

import pytest

from examchaiter.models import Answer, QuestionType
from examchaiter.output.formatter import to_display_text, to_speech_text


@pytest.mark.parametrize(
    ("qtype", "content", "display", "speech"),
    [
        (QuestionType.CHOICE, "B", "答案：B", "答案是 B"),
        (QuestionType.MULTI_CHOICE, "A B D", "答案：A B D", "答案是 A、B、D"),
        (QuestionType.FILL, "42", "填空：42", "填空：42"),
        (QuestionType.SHORT, "简答内容", "简答内容", "简答内容"),
        (QuestionType.UNKNOWN, "raw", "⚠️ 无法解析", "无法解析答案"),
    ],
)
def test_formatter_with_question_type_returns_expected_text(
    qtype: QuestionType, content: str, display: str, speech: str
) -> None:
    answer = Answer(qtype=qtype, content=content)

    assert (to_display_text(answer), to_speech_text(answer)) == (display, speech)


def test_display_text_with_choice_with_text_keeps_pure_letter() -> None:
    answer = Answer(qtype=QuestionType.CHOICE, content="B")

    assert to_display_text(answer, choice_with_text=True) == "答案：B"


def test_to_speech_text_with_question_no() -> None:
    answer = Answer(qtype=QuestionType.CHOICE, content="B")

    assert to_speech_text(answer, question_no="1") == "第 1 题，答案是 B"


def test_to_speech_text_with_question_no_for_multi_choice() -> None:
    answer = Answer(qtype=QuestionType.MULTI_CHOICE, content="A B D")

    assert to_speech_text(answer, question_no="2") == "第 2 题，答案是 A、B、D"


def test_to_speech_text_with_fallback_index() -> None:
    answer = Answer(qtype=QuestionType.SHORT, content="因为")

    assert to_speech_text(answer, fallback_index=5) == "第 5 题，因为"


def test_to_speech_text_without_number() -> None:
    answer = Answer(qtype=QuestionType.FILL, content="7")

    assert to_speech_text(answer) == "填空：7"
