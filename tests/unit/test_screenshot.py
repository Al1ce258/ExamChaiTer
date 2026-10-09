"""Unit tests for capture and perceptual hashing helpers."""

import numpy as np
import pytest
from pytest_mock import MockerFixture

from examchaiter.capture import screenshot as screenshot_module
from examchaiter.errors import CaptureError


class FakeCapture:
    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self.monitor: dict[str, int] | None = None

    def __enter__(self) -> "FakeCapture":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def grab(self, monitor: dict[str, int]) -> np.ndarray:
        self.monitor = monitor
        return self.frame


def test_grab_rect_with_valid_rect_returns_bgr_image(mocker: MockerFixture) -> None:
    frame = np.zeros((4, 5, 4), dtype=np.uint8)
    capture = FakeCapture(frame)
    mocker.patch.object(screenshot_module.mss, "mss", return_value=capture)

    image = screenshot_module.grab_rect((10, 20, 15, 24))

    assert image.shape == (4, 5, 3)


def test_grab_rect_with_valid_rect_passes_monitor_dimensions(
    mocker: MockerFixture,
) -> None:
    frame = np.zeros((4, 5, 4), dtype=np.uint8)
    capture = FakeCapture(frame)
    mocker.patch.object(screenshot_module.mss, "mss", return_value=capture)

    screenshot_module.grab_rect((10, 20, 15, 24))

    assert capture.monitor == {"left": 10, "top": 20, "width": 5, "height": 4}


def test_grab_rect_with_invalid_rect_raises_capture_error() -> None:
    with pytest.raises(CaptureError):
        screenshot_module.grab_rect((10, 20, 10, 24))


def test_grab_rect_with_non_color_frame_raises_capture_error(
    mocker: MockerFixture,
) -> None:
    capture = FakeCapture(np.zeros((4, 5), dtype=np.uint8))
    mocker.patch.object(screenshot_module.mss, "mss", return_value=capture)

    with pytest.raises(CaptureError):
        screenshot_module.grab_rect((10, 20, 15, 24))


def test_grab_window_with_valid_hwnd_passes_window_rect(
    mocker: MockerFixture,
) -> None:
    rect = (1, 2, 30, 40)
    mocker.patch.object(screenshot_module, "get_window_rect", return_value=rect)
    fake_grab = mocker.patch.object(
        screenshot_module, "grab_rect", return_value=np.zeros((38, 29, 3), dtype=np.uint8)
    )

    screenshot_module.grab_window(10)

    fake_grab.assert_called_once_with(rect)


def test_dhash_with_identical_images_returns_equal_hashes() -> None:
    image = np.tile(np.arange(9, dtype=np.uint8), (8, 1))

    assert screenshot_module.dhash(image) == screenshot_module.dhash(image.copy())


def test_dhash_with_gradient_image_returns_nonzero_hash() -> None:
    image = np.tile(np.arange(9, dtype=np.uint8), (8, 1))

    assert screenshot_module.dhash(image) != 0


def test_dhash_with_zero_hash_size_raises_value_error() -> None:
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    with pytest.raises(ValueError):
        screenshot_module.dhash(image, hash_size=0)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [(0, 0, 0), (0b1010, 0b0011, 2), (0b1111, 0, 4)],
)
def test_hamming_with_integer_hashes_returns_distance(left: int, right: int, expected: int) -> None:
    assert screenshot_module.hamming(left, right) == expected


def test_hamming_with_negative_hash_raises_value_error() -> None:
    with pytest.raises(ValueError):
        screenshot_module.hamming(-1, 0)
