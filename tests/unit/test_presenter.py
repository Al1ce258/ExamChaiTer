"""Unit tests for answer presentation and clipboard behavior."""

import sys
import types

import pytest
from pytest_mock import MockerFixture

from examchaiter.config import Settings
from examchaiter.models import Answer, PipelineResult, Question, QuestionType
from examchaiter.output.presenter import Presenter


def test_presenter_with_printer_shows_display_text(mocker: MockerFixture) -> None:
    printer = mocker.Mock()
    presenter = Presenter(Settings(_env_file=None), _printer=printer)

    presenter.show(Answer(qtype=QuestionType.CHOICE, content="B"))

    printer.assert_called_once_with("答案：B")


def test_presenter_with_clipboard_enabled_writes_answer_content(mocker: MockerFixture) -> None:
    writer = mocker.Mock()
    presenter = Presenter(
        Settings(_env_file=None, clipboard=True),
        _clipboard_writer=writer,
        _printer=mocker.Mock(),
    )

    presenter.show(Answer(qtype=QuestionType.CHOICE, content="B"))

    writer.assert_called_once_with("B")


def test_presenter_with_clipboard_disabled_does_not_write(mocker: MockerFixture) -> None:
    writer = mocker.Mock()
    presenter = Presenter(
        Settings(_env_file=None, clipboard=False),
        _clipboard_writer=writer,
        _printer=mocker.Mock(),
    )

    presenter.show(Answer(qtype=QuestionType.CHOICE, content="B"))

    writer.assert_not_called()


def test_presenter_with_clipboard_failure_does_not_raise() -> None:
    def fail_write(_text: str) -> None:
        raise RuntimeError("clipboard unavailable")

    presenter = Presenter(
        Settings(_env_file=None, clipboard=True),
        _clipboard_writer=fail_write,
        _printer=lambda _text: None,
    )

    assert presenter.show(Answer(qtype=QuestionType.CHOICE, content="B")) is None


def test_presenter_with_pipeline_result_prints_display_text(mocker: MockerFixture) -> None:
    printer = mocker.Mock()
    presenter = Presenter(Settings(_env_file=None), _printer=printer)
    result = PipelineResult(
        question=Question(text="Question"),
        answer=Answer(qtype=QuestionType.CHOICE, content="B"),
    )

    presenter.show(result)

    printer.assert_called_once_with("答案：B")


def test_presenter_with_unknown_answer_prints_unknown_message(mocker: MockerFixture) -> None:
    printer = mocker.Mock()
    presenter = Presenter(Settings(_env_file=None), _printer=printer)

    presenter.show(Answer(qtype=QuestionType.UNKNOWN, content=""))

    printer.assert_called_once_with("⚠️ 无法解析")


def test_presenter_with_fake_win32clipboard_writes_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    module = types.ModuleType("win32clipboard")
    module.OpenClipboard = lambda: calls.append(("open", None))
    module.EmptyClipboard = lambda: calls.append(("empty", None))
    module.SetClipboardData = lambda kind, value: calls.append(("set", (kind, value)))
    module.CloseClipboard = lambda: calls.append(("close", None))
    module.CF_UNICODETEXT = 13
    monkeypatch.setitem(sys.modules, "win32clipboard", module)
    presenter = Presenter(Settings(_env_file=None, clipboard=True), _printer=lambda _text: None)

    presenter.show(Answer(qtype=QuestionType.CHOICE, content="B"))

    assert ("set", (13, "B")) in calls


def test_presenter_with_unavailable_win32clipboard_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(name: str, *_args: object, **_kwargs: object) -> object:
        if name == "win32clipboard":
            raise ImportError("win32clipboard unavailable")
        return real_import(name, *_args, **_kwargs)

    import builtins

    real_import = builtins.__import__
    monkeypatch.setattr("builtins.__import__", fail_import)
    presenter = Presenter(Settings(_env_file=None, clipboard=True), _printer=lambda _text: None)

    assert presenter.show(Answer(qtype=QuestionType.CHOICE, content="B")) is None
