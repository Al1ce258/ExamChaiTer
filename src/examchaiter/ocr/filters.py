"""Filter obvious UI chrome lines before question splitting."""

from __future__ import annotations

import re

DEFAULT_UI_NOISE_PATTERNS: list[str] = [
    r".*\.(?:ini|txt)\s*$",
    (
        r"^\s*(?:(?:文件|编辑|查看|帮助|工具|格式|"
        r"File|Edit|View|Help|Tools|Format)\s+){2,}"
    ),
]
_OPTION_MARKER_RE = re.compile(r"^\s*[A-Ha-h][.、)）．:：]?\s*$")


def strip_ui_noise(text: str, patterns: list[str] | None = None) -> str:
    """Remove obvious UI chrome while keeping question and option lines."""

    if not isinstance(text, str) or not text:
        return text

    compiled: list[re.Pattern[str]] = []
    for pattern in [*DEFAULT_UI_NOISE_PATTERNS, *(patterns or [])]:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error:
            continue

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _OPTION_MARKER_RE.match(stripped):
            kept.append(line)
            continue
        if len(stripped) < 3 and not any(character.isdigit() for character in stripped):
            continue
        if any(pattern.search(stripped) for pattern in compiled):
            continue
        kept.append(line)

    if not any(line.strip() for line in kept):
        return text
    return "\n".join(kept)
