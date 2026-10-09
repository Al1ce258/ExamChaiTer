"""Unit tests for the injected answer pipeline."""

from dataclasses import dataclass, field

import numpy as np
from pytest_mock import MockerFixture

from examchaiter.config import Settings
from examchaiter.llm.client import FakeLLMClient, LLMTimeout
from examchaiter.models import OcrBlock
from examchaiter.ocr.engine import FakeOcrEngine
from examchaiter.pipeline import ExamPipeline


@dataclass
class FakeCapture:
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


class TimeoutLLM:
    def complete(self, _messages: list[dict[str, object]], *, json_mode: bool = False) -> str:
        raise LLMTimeout("timed out")


def test_run_once_happy_path_returns_choice(mocker: MockerFixture) -> None:
    result = _pipeline(mocker).run_once(1)

    assert result is not None and result.reused is False and result.answer.content == "B"


def test_run_once_dedup_hit_skips_llm(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    pipeline = _pipeline(mocker, llm=llm)

    pipeline.run_once(1)
    second = pipeline.run_once(1)

    assert second is not None and second.reused is True and len(llm.calls) == 1


def test_run_once_empty_ocr_with_vision_configured_uses_image(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    settings = Settings(_env_file=None, llm_vision_model="vision", min_text_len=1)
    pipeline = _pipeline(
        mocker,
        ocr=FakeOcrEngine(blocks=[]),
        llm=llm,
        settings=settings,
    )

    pipeline.run_once(1)

    assert "image_url" in str(llm.calls[0])


def test_run_once_empty_ocr_without_vision_returns_unknown(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(responses=[])
    pipeline = _pipeline(mocker, ocr=FakeOcrEngine(blocks=[]), llm=llm)

    result = pipeline.run_once(1)

    assert result is not None and result.answer.qtype.value == "unknown" and not llm.calls


def test_run_once_llm_timeout_returns_unknown_not_raise(mocker: MockerFixture) -> None:
    result = _pipeline(mocker, llm=TimeoutLLM()).run_once(1)

    assert result is not None and result.answer.qtype.value == "unknown"


def test_run_once_dead_window_returns_none(mocker: MockerFixture) -> None:
    result = _pipeline(mocker, capture=FakeCapture(alive=False)).run_once(1)

    assert result is None


def test_run_once_focus_failed_returns_none(mocker: MockerFixture) -> None:
    result = _pipeline(mocker, capture=FakeCapture(focus=False)).run_once(1)

    assert result is None


def test_run_once_different_image_reuses_llm(mocker: MockerFixture) -> None:
    llm = FakeLLMClient(
        responses=[
            '{"type":"choice","answer":"B"}',
            '{"type":"choice","answer":"C"}',
        ]
    )
    capture = FakeCapture()
    pipeline = _pipeline(mocker, capture=capture, llm=llm)

    first = pipeline.run_once(1)
    gradient = np.tile(np.arange(100, dtype=np.uint8), (100, 1))
    capture.img = np.repeat(gradient[:, :, np.newaxis], 3, axis=2)
    second = pipeline.run_once(1)

    assert (
        first is not None and second is not None and second.reused is False and len(llm.calls) == 2
    )


def _pipeline(
    mocker: MockerFixture,
    *,
    capture: FakeCapture | None = None,
    ocr: FakeOcrEngine | None = None,
    llm: object | None = None,
    settings: Settings | None = None,
) -> ExamPipeline:
    selected_llm = llm or FakeLLMClient(responses=['{"type":"choice","answer":"B"}'])
    selected_ocr = ocr or FakeOcrEngine(
        blocks=[OcrBlock(text="示例题目 1+1=?", bbox=(0.0, 0.0, 160.0, 20.0))]
    )
    selected_settings = settings or Settings(_env_file=None)
    return ExamPipeline(
        capture=capture or FakeCapture(),
        ocr=selected_ocr,
        llm=selected_llm,  # type: ignore[arg-type]
        settings=selected_settings,
        _clock=mocker.Mock(return_value=1.0),
        _sleep=mocker.Mock(),
    )
