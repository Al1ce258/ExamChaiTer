"""Screen capture and perceptual-hash helpers."""

from __future__ import annotations

import ctypes
from typing import Any

import mss
import numpy as np
from loguru import logger
from numpy.typing import NDArray
from PIL import Image

from examchaiter.capture.window import get_window_rect
from examchaiter.errors import CaptureError

ImageArray = NDArray[np.uint8]

_PW_RENDERFULLCONTENT = 2
_BLANK_STD_THRESHOLD = 1.0


def _load_win32_capture() -> tuple[Any, Any] | None:
    """Lazily import win32gui/win32ui; ``None`` when pywin32 is unavailable."""

    try:
        import win32gui
        import win32ui
    except ImportError:
        return None
    return win32gui, win32ui


def _print_window(hwnd: int, hdc: int, flags: int) -> bool:
    """Call ``user32.PrintWindow`` (isolated so unit tests can stub it)."""

    return bool(ctypes.windll.user32.PrintWindow(hwnd, hdc, flags))


def _is_blank(image: ImageArray) -> bool:
    """True when the frame is empty or nearly uniform (PrintWindow gave up)."""

    return image.size == 0 or float(np.std(image)) < _BLANK_STD_THRESHOLD


def _grab_window_printwindow(hwnd: int) -> ImageArray | None:
    """Render the window itself with PrintWindow; ``None`` when unusable."""

    modules = _load_win32_capture()
    if modules is None:
        return None
    win32gui, win32ui = modules
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return None
        window_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(window_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        try:
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            if not _print_window(hwnd, save_dc.GetSafeHdc(), _PW_RENDERFULLCONTENT):
                return None
            bits = bitmap.GetBitmapBits(True)
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, window_dc)
    except Exception:
        logger.warning("PrintWindow 抓取失败，降级屏幕抓取: hwnd={}", hwnd)
        return None

    frame = np.frombuffer(bits, dtype=np.uint8)
    expected = width * height * 4
    if frame.size < expected:
        return None
    frame = frame[:expected].reshape((height, width, 4))
    # GetBitmapBits 实测已是 top-down，直接取 BGR 三通道（与 mss 路径一致）。
    return np.ascontiguousarray(frame[:, :, :3])


def grab_rect(rect: tuple[int, int, int, int]) -> ImageArray:
    """Capture a screen rectangle and return a contiguous BGR image."""

    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        raise CaptureError(f"Invalid capture rectangle: {rect}")

    monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
    try:
        with mss.mss() as capture:  # pragma: no cover - real screen capture
            frame = np.array(capture.grab(monitor), dtype=np.uint8)
    except Exception as exc:
        raise CaptureError(f"Could not capture rectangle {rect}") from exc

    if frame.ndim != 3 or frame.shape[2] < 3:
        raise CaptureError("Captured frame does not contain color channels")

    return np.ascontiguousarray(frame[:, :, :3])


def _client_geometry(
    hwnd: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int], tuple[int, int]] | None:
    """Return client screen rect, window-relative offset, and client size."""

    modules = _load_win32_capture()
    if modules is None:
        return None
    win32gui, _win32ui = modules
    try:
        window_left, window_top, _window_right, _window_bottom = win32gui.GetWindowRect(hwnd)
        client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(hwnd)
        screen_left, screen_top = win32gui.ClientToScreen(hwnd, (0, 0))
    except Exception:
        logger.warning("客户区几何获取失败，降级整窗抓取: hwnd={}", hwnd)
        return None

    client_width = int(client_right - client_left)
    client_height = int(client_bottom - client_top)
    if client_width <= 0 or client_height <= 0:
        return None

    offset = (int(screen_left - window_left), int(screen_top - window_top))
    if offset[0] < 0 or offset[1] < 0:
        return None
    screen_rect = (
        int(screen_left),
        int(screen_top),
        int(screen_left + client_width),
        int(screen_top + client_height),
    )
    return screen_rect, offset, (client_width, client_height)


def _crop_client_area(
    image: ImageArray, offset_x: int, offset_y: int, client_width: int, client_height: int
) -> ImageArray:
    """Crop to the client area and pad edge pixels if PrintWindow is slightly short."""

    cropped = image[
        offset_y : offset_y + client_height,
        offset_x : offset_x + client_width,
    ]
    if cropped.size == 0:
        return cropped

    missing_y = max(0, client_height - cropped.shape[0])
    missing_x = max(0, client_width - cropped.shape[1])
    if missing_x or missing_y:
        cropped = np.pad(
            cropped,
            ((0, missing_y), (0, missing_x), (0, 0)),
            mode="edge",
        )
    return np.ascontiguousarray(cropped)


def grab_window(hwnd: int, client_only: bool = True) -> ImageArray:
    """Capture a window, preferring PrintWindow so occluded windows still work.

    Falls back to a screen grab when PrintWindow is unavailable or the rendered
    frame is blank, and raises :class:`CaptureError` when both paths fail.
    """

    geometry = _client_geometry(hwnd) if client_only else None
    image = _grab_window_printwindow(hwnd)
    if image is not None and not _is_blank(image):
        if geometry is None:
            return image
        screen_rect, (offset_x, offset_y), (client_width, client_height) = geometry
        cropped = _crop_client_area(image, offset_x, offset_y, client_width, client_height)
        if cropped.size > 0 and not _is_blank(cropped):
            return cropped
        return grab_rect(screen_rect)

    fallback_rect = geometry[0] if geometry is not None else get_window_rect(hwnd)
    return grab_rect(fallback_rect)


def dhash(image: ImageArray, hash_size: int = 8) -> int:
    """Return a deterministic difference hash for an image."""

    if hash_size < 1:
        raise ValueError("hash_size must be at least 1")

    try:
        grayscale = Image.fromarray(image).convert("L")
        resized = grayscale.resize((hash_size + 1, hash_size))
        pixels = np.asarray(resized, dtype=np.int16)
    except Exception as exc:
        raise CaptureError("Could not hash captured image") from exc

    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return value


def hamming(left: int, right: int) -> int:
    """Return the Hamming distance between two integer hashes."""

    if left < 0 or right < 0:
        raise ValueError("hashes must be non-negative")
    return (left ^ right).bit_count()
