"""Unit tests for OCR block layout."""

import pytest

from examchaiter.models import OcrBlock
from examchaiter.ocr.layout import blocks_to_text


def _block(text: str, bbox: tuple[float, float, float, float], confidence: float = 1.0) -> OcrBlock:
    return OcrBlock(text=text, bbox=bbox, confidence=confidence)


def test_blocks_to_text_with_empty_blocks_returns_empty_string() -> None:
    assert blocks_to_text([]) == ""


def test_blocks_to_text_with_single_block_returns_text() -> None:
    assert blocks_to_text([_block("Only", (10.0, 10.0, 50.0, 20.0))]) == "Only"


def test_blocks_to_text_with_same_row_sorts_by_x() -> None:
    blocks = [
        _block("Right", (100.0, 0.0, 160.0, 20.0)),
        _block("Left", (0.0, 1.0, 50.0, 21.0)),
    ]

    assert blocks_to_text(blocks) == "Left Right"


def test_blocks_to_text_with_two_rows_sorts_by_y() -> None:
    blocks = [
        _block("Second", (0.0, 100.0, 60.0, 120.0)),
        _block("First", (0.0, 0.0, 50.0, 20.0)),
    ]

    assert blocks_to_text(blocks) == "First\nSecond"


def test_blocks_to_text_with_close_y_and_reversed_x_sorts_by_x() -> None:
    blocks = [
        _block("Right", (100.0, 0.0, 160.0, 20.0)),
        _block("Left", (0.0, 2.0, 50.0, 22.0)),
    ]

    assert blocks_to_text(blocks) == "Left Right"


def test_blocks_to_text_with_low_confidence_block_keeps_text() -> None:
    blocks = [_block("Noise", (0.0, 0.0, 50.0, 20.0), confidence=0.01)]

    assert blocks_to_text(blocks) == "Noise"


@pytest.mark.parametrize(
    ("line_gap_ratio", "expected"),
    [(0.1, "Left\nRight"), (2.0, "Left Right")],
)
def test_blocks_to_text_with_line_gap_ratio_changes_rows(
    line_gap_ratio: float, expected: str
) -> None:
    blocks = [
        _block("Left", (0.0, 0.0, 50.0, 20.0)),
        _block("Right", (100.0, 10.0, 160.0, 30.0)),
    ]

    assert blocks_to_text(blocks, line_gap_ratio=line_gap_ratio) == expected
