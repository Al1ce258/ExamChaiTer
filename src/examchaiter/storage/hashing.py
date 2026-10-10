"""Pure text normalization helpers used for question de-duplication."""

from __future__ import annotations

import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)

# Full-width ASCII (0xFF01-0xFF5E) already collapses to its half-width form in
# ``_to_halfwidth``; the remaining CJK punctuation is mapped explicitly.
_PUNCTUATION_MAP = str.maketrans(
    {
        "【": "[",
        "】": "]",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)


def _to_halfwidth(text: str) -> str:
    """Convert full-width ASCII and the ideographic space to their ASCII forms."""
    converted: list[str] = []
    for char in text:
        code = ord(char)
        if code == 0x3000:
            converted.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            converted.append(chr(code - 0xFEE0))
        else:
            converted.append(char)
    return "".join(converted)


def _lowercase_ascii(text: str) -> str:
    """Lower-case ASCII letters only, leaving non-ASCII characters untouched."""
    return "".join(chr(ord(char) + 32) if "A" <= char <= "Z" else char for char in text)


def normalize_text(text: str) -> str:
    """Return a canonical form of ``text`` for hashing.

    Removes every whitespace character, folds full-width ASCII to half-width,
    lower-cases ASCII letters, and unifies CJK punctuation with ASCII.
    """
    folded = _to_halfwidth(text)
    folded = _WHITESPACE_RE.sub("", folded)
    folded = folded.translate(_PUNCTUATION_MAP)
    return _lowercase_ascii(folded)


def question_hash(text: str) -> str:
    """Return the SHA-256 hex digest of the normalized ``text``."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
