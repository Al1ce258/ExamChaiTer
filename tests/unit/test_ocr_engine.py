"""Unit tests for OCR engine adapters."""

import numpy as np
import pytest
from pytest_mock import MockerFixture

from examchaiter.models import OcrBlock
from examchaiter.ocr import engine as engine_module
from examchaiter.ocr.engine import FakeOcrEngine, OcrFailed


def test_fake_ocr_engine_with_blocks_returns_preconfigured_blocks() -> None:
    blocks = [OcrBlock(text="Question", bbox=(1.0, 2.0, 30.0, 12.0), confidence=0.8)]

    assert FakeOcrEngine(blocks=blocks).recognize(_image()) == blocks


def test_rapid_ocr_engine_with_import_failure_raises_ocr_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(_name: str) -> object:
        raise ImportError("rapidocr unavailable")

    monkeypatch.setattr(engine_module.importlib, "import_module", fail_import)

    with pytest.raises(OcrFailed):
        engine_module.RapidOcrEngine()


def test_rapid_ocr_engine_with_backend_result_returns_blocks(mocker: MockerFixture) -> None:
    backend = mocker.Mock(
        return_value=(
            [
                [
                    [[0, 0], [20, 0], [20, 10], [0, 10]],
                    "Detected",
                    0.95,
                ]
            ],
            0.1,
        )
    )
    engine = object.__new__(engine_module.RapidOcrEngine)
    engine._engine = backend

    blocks = engine.recognize(_image())

    assert blocks == [OcrBlock(text="Detected", bbox=(0.0, 0.0, 20.0, 10.0), confidence=0.95)]


def test_rapid_ocr_engine_with_backend_failure_raises_ocr_failed(
    mocker: MockerFixture,
) -> None:
    backend = mocker.Mock(side_effect=RuntimeError("backend failed"))
    engine = object.__new__(engine_module.RapidOcrEngine)
    engine._engine = backend

    with pytest.raises(OcrFailed):
        engine.recognize(_image())


def _image() -> engine_module.ImageArray:
    return np.zeros((8, 8, 3), dtype=np.uint8)
