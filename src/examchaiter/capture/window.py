"""Windows top-level window discovery and focus helpers."""

from __future__ import annotations

import re
import time
from typing import cast

import win32con
import win32gui

from examchaiter.errors import WindowError
from examchaiter.models import WindowInfo

WindowRect = tuple[int, int, int, int]


def list_windows(title_filter: str | None = None) -> list[WindowInfo]:
    """Return visible, titled top-level windows matching an optional regex."""

    pattern: re.Pattern[str] | None = None
    if title_filter is not None:
        try:
            pattern = re.compile(title_filter, re.IGNORECASE)
        except re.error as exc:
            raise WindowError(f"Invalid title filter: {title_filter}") from exc

    windows: list[WindowInfo] = []

    def collect(hwnd: int, _extra: object) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True

        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        if pattern is not None and pattern.search(title) is None:
            return True

        rect = cast(WindowRect, tuple(win32gui.GetWindowRect(hwnd)))
        windows.append(WindowInfo(hwnd=hwnd, title=title, rect=rect))
        return True

    win32gui.EnumWindows(collect, None)
    return windows


def find_window(title_filter: str) -> WindowInfo | None:
    """Return the first window whose title matches the given regex."""

    matches = list_windows(title_filter)
    return matches[0] if matches else None


def focus_window(hwnd: int, retries: int = 3) -> bool:
    """Restore and focus a window, retrying until it becomes foreground."""

    for attempt in range(max(0, retries)):
        if not is_window_alive(hwnd):
            return False

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            if win32gui.GetForegroundWindow() == hwnd:
                return True
        except Exception:
            pass

        if attempt + 1 < retries:
            time.sleep(0.05)

    return False


def get_window_rect(hwnd: int) -> WindowRect:
    """Return the window rectangle as ``(left, top, right, bottom)``."""

    if not is_window_alive(hwnd):
        raise WindowError(f"Window {hwnd} is not alive")

    try:
        return cast(WindowRect, tuple(win32gui.GetWindowRect(hwnd)))
    except Exception as exc:
        raise WindowError(f"Could not read rectangle for window {hwnd}") from exc


def is_window_alive(hwnd: int) -> bool:
    """Return whether ``hwnd`` still identifies a live window."""

    return bool(win32gui.IsWindow(hwnd))
