"""Convert OCR blocks into reading-order text."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean

from examchaiter.models import OcrBlock


def _center_y(block: OcrBlock) -> float:
    return (block.bbox[1] + block.bbox[3]) / 2.0


def _left(block: OcrBlock) -> float:
    return block.bbox[0]


def _height(block: OcrBlock) -> float:
    return max(0.0, block.bbox[3] - block.bbox[1])


def blocks_to_text(blocks: Sequence[OcrBlock], line_gap_ratio: float = 0.6) -> str:
    """Cluster blocks into rows and return text in natural reading order."""

    if not blocks:
        return ""

    threshold = fmean(_height(block) for block in blocks) * line_gap_ratio
    ordered = sorted(blocks, key=lambda block: (_center_y(block), _left(block)))

    rows: list[list[OcrBlock]] = []
    row_centers: list[float] = []
    for block in ordered:
        center = _center_y(block)
        if not rows or abs(center - row_centers[-1]) > threshold:
            rows.append([block])
            row_centers.append(center)
            continue

        rows[-1].append(block)
        row_centers[-1] = fmean(_center_y(item) for item in rows[-1])

    return "\n".join(
        " ".join(
            block.text for block in sorted(row, key=lambda item: (_left(item), _center_y(item)))
        )
        for row in rows
    )
