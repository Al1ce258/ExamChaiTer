"""Integration tests for Qt GUI widgets using pytest-qt."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pytest_mock import MockerFixture

from examchaiter.config import Settings
from examchaiter.gui.main_window import MainWindow
from examchaiter.gui.overlay import OverlayWindow
from examchaiter.models import Answer, PipelineResult, Question, QuestionType, WindowInfo

pytestmark = pytest.mark.integration


def _result(no: str = "1", content: str = "B", *, reused: bool = False) -> PipelineResult:
    return PipelineResult(
        question=Question(text="What is 1+1?"),
        answer=Answer(qtype=QuestionType.CHOICE, content=content),
        reused=reused,
        question_no=no,
    )


def _controller(mocker: MockerFixture) -> object:
    controller = mocker.MagicMock()
    controller.list_windows.return_value = [
        WindowInfo(hwnd=1, title="Exam", rect=(0, 0, 100, 100)),
        WindowInfo(hwnd=2, title="Chat", rect=(0, 0, 100, 100)),
    ]
    controller.state.last_results = [_result("1", "B")]
    controller.state.last_answer = Answer(qtype=QuestionType.CHOICE, content="B")
    controller.state.last_question_text = "Question preview"
    controller.is_tts_running.return_value = False
    controller.is_auto_running.return_value = False
    return controller


def test_main_window_with_buttons_answers_once(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    qtbot.mouseClick(window.answer_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    qtbot.waitUntil(lambda: controller.answer_once.call_count == 1, timeout=1000)  # type: ignore[attr-defined]
    controller.answer_once.assert_called_once()


def test_main_window_refresh_populates_combo(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.window_combo.count() == 2


def test_main_window_toggle_button_text_changes(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    controller.is_tts_running.side_effect = [False, True]
    controller.toggle_tts.return_value = True
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    qtbot.mouseClick(window.toggle_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert window.toggle_button.text() == "停止朗读"


def test_main_window_close_event_only_hides(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()

    window.close()

    assert window.isVisible() is False


def test_overlay_show_answer_updates_label(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    overlay = OverlayWindow(controller)  # type: ignore[arg-type]
    qtbot.addWidget(overlay)  # type: ignore[attr-defined]

    overlay.show_answer()

    assert overlay.answer_label.text() == "B"


def test_main_window_uses_qss(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    app = QApplication.instance()

    assert app is not None and "#0078D4" in app.styleSheet()


def test_auto_toggle_calls_start_stop(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    controller.is_auto_running.return_value = True
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    qtbot.mouseClick(window.auto_checkbox, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    window.auto_checkbox.click()
    started = controller.start_auto.called
    window.auto_checkbox.click()

    assert (started, controller.stop_auto.called) == (True, True)


def test_answer_ready_updates_status_bar(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.bridge.answer_ready.emit(_result("2", "C", reused=True), True)

    message = window.statusBar().currentMessage()
    assert message.startswith("已作答")
    assert "[2]" in message
    assert "缓存" in message


def test_round_done_updates_answer_list(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.bridge.round_done.emit(
        [_result("1", "A"), _result("2", "B", reused=True), _result("", "C")]
    )

    assert window.answer_list.row_texts() == ["[1] A", "[2] B  · 缓存", "[?] C"]


def test_manual_answer_shows_multiple_items(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    controller.answer_once.return_value = [
        _result("1", "A"),
        _result("2", "B"),
        _result("3", "C"),
    ]
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    qtbot.mouseClick(window.answer_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: len(window.answer_list.row_texts()) == 3, timeout=1000)  # type: ignore[attr-defined]

    assert window.answer_list.row_texts() == ["[1] A", "[2] B", "[3] C"]


def test_error_signal_shows_messagebox(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    warning = mocker.patch("PySide6.QtWidgets.QMessageBox.warning")

    window.bridge.error_occurred.emit(RuntimeError("boom"))

    assert warning.call_count == 1


def test_answer_list_empty_state_shows_hint(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    controller.state.last_results = []
    controller.state.last_question_text = ""
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.answer_list.row_texts() == ["等待作答"]


def test_answer_list_shows_state_results(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    controller.state.last_results = [_result("3", "B")]
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.answer_list.row_texts() == ["[3] B"]


def test_status_bar_is_chinese(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    messages: dict[str, str] = {}

    for state in ("idle", "running", "stopping", "stopped", "error"):
        window.bridge.state_changed.emit(state)
        messages[state] = window.statusBar().currentMessage()

    assert messages == {
        "idle": "就绪",
        "running": "自动模式运行中",
        "stopping": "正在停止…",
        "stopped": "自动模式已停止",
        "error": "错误",
    }
