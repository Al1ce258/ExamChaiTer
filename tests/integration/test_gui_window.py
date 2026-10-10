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


def _controller(mocker: MockerFixture) -> object:
    controller = mocker.MagicMock()
    controller.list_windows.return_value = [
        WindowInfo(hwnd=1, title="Exam", rect=(0, 0, 100, 100)),
        WindowInfo(hwnd=2, title="Chat", rect=(0, 0, 100, 100)),
    ]
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


def test_answer_ready_updates_labels(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    result = PipelineResult(
        question=Question(text="What is 1+1?"),
        answer=Answer(qtype=QuestionType.CHOICE, content="B"),
    )

    window.bridge.answer_ready.emit(result, False)

    assert (window.answer_label.text(), window.preview_edit.toPlainText()) == (
        "B",
        "What is 1+1?",
    )


def test_error_signal_shows_messagebox(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    window = MainWindow(controller, Settings(_env_file=None))  # type: ignore[arg-type]
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    warning = mocker.patch("PySide6.QtWidgets.QMessageBox.warning")

    window.bridge.error_occurred.emit(RuntimeError("boom"))

    assert warning.call_count == 1
