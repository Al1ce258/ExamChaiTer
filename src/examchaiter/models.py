"""Shared domain models."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QuestionType(StrEnum):
    """Supported answer shapes."""

    CHOICE = "choice"
    FILL = "fill"
    SHORT = "short"
    UNKNOWN = "unknown"


class WindowInfo(_FrozenModel):
    """A Windows top-level window and its screen rectangle."""

    hwnd: int
    title: str
    rect: tuple[int, int, int, int]


class OcrBlock(_FrozenModel):
    """One recognized text region and its confidence score."""

    text: str
    bbox: tuple[float, float, float, float]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Question(_FrozenModel):
    """Text and optional image inputs extracted for one question."""

    text: str
    qtype: QuestionType = QuestionType.UNKNOWN
    images: tuple[bytes, ...] = ()


class Answer(_FrozenModel):
    """The only public answer payload; content must remain a pure answer."""

    qtype: QuestionType
    content: str


class PipelineResult(_FrozenModel):
    """One pipeline result and whether it was reused without calling the LLM."""

    answer: Answer
    reused: bool = False
