"""Console and clipboard answer presentation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from loguru import logger

from examchaiter.config import Settings
from examchaiter.models import Answer
from examchaiter.output.formatter import to_display_text

ClipboardWriter = Callable[[str], None]


class Presenter:
    """Render an answer and optionally copy its content."""

    def __init__(
        self,
        settings: Settings,
        _clipboard_writer: ClipboardWriter | None = None,
        _printer: Callable[[str], object] = print,
    ) -> None:
        self.settings = settings
        self._clipboard_writer = _clipboard_writer
        self._printer = _printer

    def show(self, answer: Answer) -> None:
        self._printer(to_display_text(answer))
        if not self.settings.clipboard:
            return

        writer = self._clipboard_writer or _load_clipboard_writer()
        try:
            writer(answer.content)
        except Exception:
            logger.warning("Clipboard write failed")


def _load_clipboard_writer() -> ClipboardWriter:
    def write(text: str) -> None:
        import win32clipboard

        clipboard = cast(Any, win32clipboard)

        clipboard.OpenClipboard()
        try:
            clipboard.EmptyClipboard()
            clipboard.SetClipboardData(clipboard.CF_UNICODETEXT, text)
        finally:
            clipboard.CloseClipboard()

    return write
