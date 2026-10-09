"""Unit tests for window discovery and focus helpers."""

import pytest
from pytest_mock import MockerFixture

from examchaiter.__main__ import main
from examchaiter.capture import window as window_module
from examchaiter.errors import WindowError
from examchaiter.models import WindowInfo


def _install_fake_windows(
    mocker: MockerFixture,
    titles: dict[int, str],
    rects: dict[int, tuple[int, int, int, int]],
) -> None:
    def enum_windows(callback: object, _extra: object) -> None:
        for hwnd in titles:
            callback(hwnd, None)  # type: ignore[operator]

    mocker.patch.object(window_module.win32gui, "EnumWindows", side_effect=enum_windows)
    mocker.patch.object(window_module.win32gui, "IsWindowVisible", return_value=True)
    mocker.patch.object(window_module.win32gui, "GetWindowText", side_effect=titles.get)
    mocker.patch.object(window_module.win32gui, "GetWindowRect", side_effect=rects.get)


def test_list_windows_with_title_filter_returns_single_match(mocker: MockerFixture) -> None:
    _install_fake_windows(
        mocker,
        {10: "Exam Window", 20: "Chat Window"},
        {10: (0, 0, 100, 100), 20: (0, 0, 200, 200)},
    )

    windows = window_module.list_windows("exam")

    assert windows == [WindowInfo(hwnd=10, title="Exam Window", rect=(0, 0, 100, 100))]


def test_list_windows_without_filter_returns_all_titled_windows(
    mocker: MockerFixture,
) -> None:
    _install_fake_windows(
        mocker,
        {10: "Exam Window", 20: "Chat Window"},
        {10: (0, 0, 100, 100), 20: (0, 0, 200, 200)},
    )

    assert len(window_module.list_windows()) == 2


def test_list_windows_with_invalid_regex_raises_window_error() -> None:
    with pytest.raises(WindowError):
        window_module.list_windows("[")


def test_find_window_with_match_returns_first_window(mocker: MockerFixture) -> None:
    expected = WindowInfo(hwnd=10, title="Exam Window", rect=(0, 0, 100, 100))
    mocker.patch.object(window_module, "list_windows", return_value=[expected])

    assert window_module.find_window("Exam") == expected


def test_find_window_without_match_returns_none(mocker: MockerFixture) -> None:
    mocker.patch.object(window_module, "list_windows", return_value=[])

    assert window_module.find_window("Missing") is None


def test_focus_window_with_foreground_success_returns_true(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(window_module, "is_window_alive", return_value=True)
    fake_show = mocker.patch.object(window_module.win32gui, "ShowWindow")
    mocker.patch.object(window_module.win32con, "SW_RESTORE", 9)
    mocker.patch.object(window_module.win32gui, "SetForegroundWindow")
    mocker.patch.object(window_module.win32gui, "GetForegroundWindow", return_value=10)

    window_module.focus_window(10)

    assert fake_show.call_args.args == (10, 9)


def test_focus_window_with_dead_window_returns_false(mocker: MockerFixture) -> None:
    mocker.patch.object(window_module, "is_window_alive", return_value=False)

    assert window_module.focus_window(10) is False


def test_focus_window_with_repeated_failure_returns_false(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(window_module, "is_window_alive", return_value=True)
    mocker.patch.object(window_module.win32gui, "ShowWindow")
    mocker.patch.object(window_module.win32gui, "SetForegroundWindow")
    mocker.patch.object(window_module.win32gui, "GetForegroundWindow", return_value=99)
    mocker.patch.object(window_module.time, "sleep")

    assert window_module.focus_window(10, retries=2) is False


def test_get_window_rect_with_live_window_returns_rect(mocker: MockerFixture) -> None:
    mocker.patch.object(window_module, "is_window_alive", return_value=True)
    mocker.patch.object(window_module.win32gui, "GetWindowRect", return_value=(1, 2, 301, 202))

    assert window_module.get_window_rect(10) == (1, 2, 301, 202)


def test_get_window_rect_with_dead_window_raises_window_error(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(window_module, "is_window_alive", return_value=False)

    with pytest.raises(WindowError):
        window_module.get_window_rect(10)


def test_is_window_alive_with_valid_handle_returns_true(mocker: MockerFixture) -> None:
    mocker.patch.object(window_module.win32gui, "IsWindow", return_value=1)

    assert window_module.is_window_alive(10) is True


def test_list_windows_command_with_filter_passes_filter(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_list = mocker.patch.object(window_module, "list_windows", return_value=[])

    main(["list-windows", "--filter", "Exam"])

    capsys.readouterr()
    fake_list.assert_called_once_with("Exam")


def test_list_windows_command_with_windows_prints_handle(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_window = WindowInfo(hwnd=10, title="Exam Window", rect=(0, 0, 100, 100))
    mocker.patch.object(window_module, "list_windows", return_value=[fake_window])

    main(["list-windows"])

    assert "0x0000000A\tExam Window\t0,0,100,100" in capsys.readouterr().out
