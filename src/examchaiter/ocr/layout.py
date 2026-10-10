"""Convert OCR blocks into reading-order text."""

from __future__ import annotations

import re
from collections.abc import Sequence
from statistics import fmean

from examchaiter.models import OcrBlock


def _center_y(block: OcrBlock) -> float:
    return (block.bbox[1] + block.bbox[3]) / 2.0


def _left(block: OcrBlock) -> float:
    return block.bbox[0]


def _height(block: OcrBlock) -> float:
    return max(0.0, block.bbox[3] - block.bbox[1])


_OPTION_MARKER_RE = re.compile(r"^\s*([A-Ha-h])(?:\s*[.、)）．:：]\s*|\s+)(.*\S)\s*$")
_CHOICE_HINT_RE = re.compile(r"单选|多选|选择|下列|哪个|哪些|哪项|正确|错误|不是|最适合|适合")
_STOP_LINE_RE = re.compile(
    r"^\s*(?:单选题|多选题|判断题|不定项选择题|交卷|提交|答题卡|下一题|上一题)\s*$"
)
_NUMBERED_LINE_RE = re.compile(r"^\s*\d+(?:\s*[.、)）．:：]|\s+[\u4e00-\u9fffA-Za-z])")
_STRAY_MARKER_PREFIX_RE = re.compile(r"^\s*[)）]\s*")
_MISREAD_FIRST_OPTION_RE = re.compile(r"^\s*[Pp]\s+")
_CHOICE_LETTERS = ("A", "B", "C", "D")
_MAX_OPTION_LINE_LEN = 120


def _split_option_marker(line: str) -> tuple[str, str] | None:
    match = _OPTION_MARKER_RE.match(line)
    if match is None:
        return None
    body = match.group(2).strip()
    if not body:
        return None
    return match.group(1).upper(), body


def _looks_like_option_line(line: str) -> bool:
    text = line.strip()
    if not text or len(text) > _MAX_OPTION_LINE_LEN:
        return False
    if _STOP_LINE_RE.match(text) is not None:
        return False
    return not (text.endswith(("?", "？")) and _split_option_marker(text) is None)


def _has_choice_context(lines: Sequence[str], start: int, length: int) -> bool:
    before = "\n".join(lines[max(0, start - 2) : start])
    after = "\n".join(lines[start + length : start + length + 2])
    return _CHOICE_HINT_RE.search(f"{before}\n{after}") is not None


def _has_choice_boundary(lines: Sequence[str], start: int, length: int) -> bool:
    before = lines[start - 1].strip() if start > 0 else ""
    after_index = start + length
    after = lines[after_index].strip() if after_index < len(lines) else ""
    return (
        _CHOICE_HINT_RE.search(before) is not None
        or not after
        or _STOP_LINE_RE.match(after) is not None
    )


def _strip_missing_marker(line: str, expected_letter: str, offset: int) -> str:
    text = _STRAY_MARKER_PREFIX_RE.sub("", line.strip())
    if offset == 0:
        text = _MISREAD_FIRST_OPTION_RE.sub("", text)
    if text.startswith(expected_letter) and len(text) > 1 and text[1].islower():
        text = text[1:].lstrip()
    return text


def _valid_option_block(lines: Sequence[str], start: int, length: int) -> bool:
    block = lines[start : start + length]
    if len(block) != length or not all(_looks_like_option_line(line) for line in block):
        return False

    markers = 0
    for offset, line in enumerate(block):
        marker = _split_option_marker(line)
        if marker is None:
            continue
        if marker[0] != _CHOICE_LETTERS[offset]:
            return False
        markers += 1

    if markers >= 2:
        return True
    if not _has_choice_context(lines, start, length):
        return False
    if length != len(_CHOICE_LETTERS):
        return False
    if any(_NUMBERED_LINE_RE.match(line) for line in block):
        return False
    return markers != 0 or _has_choice_boundary(lines, start, length)


def _normalize_option_lines(lines: Sequence[str]) -> list[str]:
    normalized = list(lines)
    index = 0
    while index < len(normalized):
        matched = False
        for length in range(len(_CHOICE_LETTERS), 1, -1):
            if index + length > len(normalized):
                continue
            if not _valid_option_block(normalized, index, length):
                continue
            for offset, line in enumerate(normalized[index : index + length]):
                expected_letter = _CHOICE_LETTERS[offset]
                marker = _split_option_marker(line)
                body = marker[1] if marker is not None else line
                repaired = _strip_missing_marker(body, expected_letter, offset)
                normalized[index + offset] = f"{expected_letter}. {repaired}"
            index += length
            matched = True
            break
        if not matched:
            index += 1
    return normalized


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

    lines = [
        " ".join(
            block.text for block in sorted(row, key=lambda item: (_left(item), _center_y(item)))
        )
        for row in rows
    ]
    return "\n".join(_normalize_option_lines(lines))
