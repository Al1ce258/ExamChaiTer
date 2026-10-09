"""OCR engine protocol, production adapter, and fake implementation."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from examchaiter.errors import OcrError
from examchaiter.models import OcrBlock

ImageArray = NDArray[np.uint8]
OcrFailed = OcrError


class OcrEngine(Protocol):
    """Protocol implemented by OCR adapters and test doubles."""

    def recognize(self, img: ImageArray) -> list[OcrBlock]: ...


@dataclass
class FakeOcrEngine:
    """Return a fixed block list without loading OCR dependencies."""

    blocks: list[OcrBlock] = field(default_factory=list)

    def recognize(self, _img: ImageArray) -> list[OcrBlock]:
        return list(self.blocks)


class RapidOcrEngine:
    """Lazy RapidOCR adapter that converts backend output to OcrBlock values."""

    def __init__(self) -> None:
        self._engine: Any = self._load_engine()

    @staticmethod
    def _load_engine() -> Any:
        try:
            module = importlib.import_module("rapidocr_onnxruntime")
            rapid_ocr_class = module.RapidOCR  # pragma: no cover - real OCR backend
            return rapid_ocr_class()  # pragma: no cover - real OCR backend
        except Exception as exc:
            raise OcrFailed("RapidOCR is unavailable or could not be initialized") from exc

    def recognize(self, img: ImageArray) -> list[OcrBlock]:
        try:
            raw_result, _elapsed = self._engine(img)
            return self._parse_result(raw_result)
        except Exception as exc:
            raise OcrFailed("RapidOCR recognition failed") from exc

    @staticmethod
    def _parse_result(raw_result: Any) -> list[OcrBlock]:
        if not raw_result:
            return []

        blocks: list[OcrBlock] = []
        for item in raw_result:
            box = item[0]
            text = str(item[1])
            confidence = float(item[2])
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            blocks.append(
                OcrBlock(
                    text=text,
                    bbox=(min(xs), min(ys), max(xs), max(ys)),
                    confidence=confidence,
                )
            )
        return blocks
