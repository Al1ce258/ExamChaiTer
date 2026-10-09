"""Offline fake fixtures shared by unit tests."""

from dataclasses import dataclass, field

import numpy as np
import pytest

from examchaiter.config import Settings
from examchaiter.llm.client import FakeLLMClient
from examchaiter.models import OcrBlock
from examchaiter.ocr.engine import FakeOcrEngine
from examchaiter.output.presenter import Presenter


@dataclass
class FakeCapture:
    """Synthetic capture source that never reads the screen."""

    rect: tuple[int, int, int, int] = (0, 0, 100, 100)
    img: np.ndarray = field(default_factory=lambda: np.full((100, 100, 3), 255, dtype=np.uint8))
    alive: bool = True
    focus: bool = True

    def get_window_rect(self, _hwnd: int) -> tuple[int, int, int, int]:
        return self.rect

    def is_window_alive(self, _hwnd: int) -> bool:
        return self.alive

    def focus_window(self, _hwnd: int) -> bool:
        return self.focus

    def grab_window(self, _hwnd: int) -> np.ndarray:
        return self.img.copy()


@dataclass
class FakeSpeaker:
    """Speaker double that records text without using an audio device."""

    spoken: list[str] = field(default_factory=list)

    def speak(self, text: str) -> None:
        self.spoken.append(text)


@pytest.fixture
def fake_capture() -> FakeCapture:
    return FakeCapture()


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
def fake_presenter(settings: Settings) -> Presenter:
    return Presenter(settings, _printer=lambda _text: None)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)
    return Settings(_env_file=None)
