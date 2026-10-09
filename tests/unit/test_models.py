"""Unit tests for the shared domain models."""

import pytest
from pydantic import ValidationError

from examchaiter.errors import ConfigurationError, ExamChaiTerError
from examchaiter.models import (
    Answer,
    OcrBlock,
    PipelineResult,
    Question,
    QuestionType,
    WindowInfo,
)


@pytest.mark.parametrize(
    ("question_type", "expected"),
    [
        (QuestionType.CHOICE, "choice"),
        (QuestionType.FILL, "fill"),
        (QuestionType.SHORT, "short"),
        (QuestionType.UNKNOWN, "unknown"),
    ],
)
def test_question_type_with_value_serializes_expected(
    question_type: QuestionType, expected: str
) -> None:
    assert question_type.value == expected


def test_window_info_with_rect_stores_hwnd() -> None:
    window = WindowInfo(hwnd=42, title="Exam", rect=(1, 2, 301, 202))

    assert window.hwnd == 42


def test_ocr_block_with_valid_confidence_stores_text() -> None:
    block = OcrBlock(text="A", bbox=(0.0, 0.0, 1.0, 1.0), confidence=0.9)

    assert block.text == "A"


def test_ocr_block_with_confidence_above_one_rejects_value() -> None:
    with pytest.raises(ValidationError):
        OcrBlock(text="A", bbox=(0.0, 0.0, 1.0, 1.0), confidence=1.01)


def test_question_without_images_defaults_to_empty_tuple() -> None:
    question = Question(text="Question")

    assert question.images == ()


def test_answer_with_choice_type_preserves_content() -> None:
    answer = Answer(qtype=QuestionType.CHOICE, content="B")

    assert answer.content == "B"


def test_pipeline_result_without_reuse_defaults_to_false() -> None:
    result = PipelineResult(
        question=Question(text="Question"),
        answer=Answer(qtype=QuestionType.FILL, content="42"),
    )

    assert result.reused is False


def test_pipeline_result_with_reuse_stores_true() -> None:
    result = PipelineResult(
        question=Question(text="Question"),
        answer=Answer(qtype=QuestionType.SHORT, content="answer"),
        reused=True,
    )

    assert result.reused is True


def test_window_info_mutation_raises_validation_error() -> None:
    window = WindowInfo(hwnd=42, title="Exam", rect=(1, 2, 301, 202))

    with pytest.raises(ValidationError):
        window.title = "Changed"


def test_configuration_error_subclasses_examchaiter_error() -> None:
    assert issubclass(ConfigurationError, ExamChaiTerError)
