"""Integration test for the real RapidOCR adapter."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from examchaiter.ocr.engine import RapidOcrEngine
from examchaiter.ocr.layout import blocks_to_text

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def real_ocr_text() -> str:
    image_path = Path(__file__).parents[1] / "fixtures" / "synthetic_question.png"
    with Image.open(image_path) as source:
        image = np.asarray(source.convert("RGB"), dtype=np.uint8)
    return blocks_to_text(RapidOcrEngine().recognize(image))


@pytest.mark.parametrize("keyword", ["第一行", "题目示例", "Second", "line", "sample", "12345"])
def test_real_rapid_ocr_with_synthetic_image_contains_keyword(
    real_ocr_text: str, keyword: str
) -> None:
    assert keyword in real_ocr_text
