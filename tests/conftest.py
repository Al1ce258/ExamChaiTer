"""Offline fake fixtures shared by unit tests."""

from dataclasses import dataclass, field

import numpy as np
import pytest

from examchaiter.config import Settings
from examchaiter.models import OcrBlock


@dataclass
class FakeCapture:
    """Synthetic frame source that never reads the screen."""

    frame: np.ndarray

    def grab(self) -> np.ndarray:
        return self.frame.copy()


@dataclass
class FakeOcrEngine:
    """OCR double that returns pre-built blocks."""

    blocks: list[OcrBlock]

    def recognize(self, _image: np.ndarray) -> list[OcrBlock]:
        return list(self.blocks)


@dataclass
class FakeLLMClient:
    """LLM double that returns queued responses in order."""

    responses: list[str]
    calls: list[list[dict[str, str]]] = field(default_factory=list)

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if not self.responses:
            raise LookupError("FakeLLMClient has no queued response")
        return self.responses.pop(0)


@dataclass
class FakeSpeaker:
    """Speaker double that records text without using an audio device."""

    spoken: list[str] = field(default_factory=list)

    def speak(self, text: str) -> None:
        self.spoken.append(text)


@pytest.fixture
def fake_capture() -> FakeCapture:
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    return FakeCapture(frame=frame)


@pytest.fixture
def fake_ocr() -> FakeOcrEngine:
    return FakeOcrEngine(
        blocks=[
            OcrBlock(text="1 + 1 =", bbox=(0.0, 0.0, 40.0, 12.0), confidence=0.99),
            OcrBlock(text="A. 1\nB. 2", bbox=(0.0, 16.0, 40.0, 32.0), confidence=0.98),
        ]
    )


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])


@pytest.fixture
def fake_speaker() -> FakeSpeaker:
    return FakeSpeaker()


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)
    return Settings(_env_file=None)
