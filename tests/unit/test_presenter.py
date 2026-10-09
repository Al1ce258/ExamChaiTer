"""Unit tests for answer presentation and clipboard behavior."""

from pytest_mock import MockerFixture

from examchaiter.config import Settings
from examchaiter.models import Answer, QuestionType
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
