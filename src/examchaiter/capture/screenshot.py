"""Screen capture and perceptual-hash helpers."""

from __future__ import annotations

import mss
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from examchaiter.capture.window import get_window_rect
from examchaiter.errors import CaptureError

ImageArray = NDArray[np.uint8]


def grab_rect(rect: tuple[int, int, int, int]) -> ImageArray:
    """Capture a screen rectangle and return a contiguous BGR image."""

    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        raise CaptureError(f"Invalid capture rectangle: {rect}")

    monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}
    try:
        with mss.mss() as capture:
            frame = np.array(capture.grab(monitor), dtype=np.uint8)
    except Exception as exc:
        raise CaptureError(f"Could not capture rectangle {rect}") from exc

    if frame.ndim != 3 or frame.shape[2] < 3:
        raise CaptureError("Captured frame does not contain color channels")

    return np.ascontiguousarray(frame[:, :, :3])


def grab_window(hwnd: int) -> ImageArray:
    """Capture the current rectangle of a window."""

    return grab_rect(get_window_rect(hwnd))


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
