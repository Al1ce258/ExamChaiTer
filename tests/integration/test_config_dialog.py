"""Integration tests for the configuration dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox
from pytest_mock import MockerFixture

from examchaiter.gui.config_dialog import ConfigDialog
from examchaiter.storage.config_store import AppConfig

pytestmark = pytest.mark.integration


def _controller(mocker: MockerFixture) -> object:
    controller = mocker.MagicMock()
    controller.get_config.return_value = AppConfig(
        llm_base_url="https://api.deepseek.com/v1",
        llm_api_key="sk-stored",
        llm_model="deepseek-chat",
        llm_vision_model="vision-x",
        tts_rate=200,
        auto_poll_interval=2.5,
        auto_speak_choice_repeat=6,
        auto_speak_fill_repeat=4,
    )
    return controller


def test_dialog_loads_config_into_fields(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = ConfigDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert (
        dialog.base_url_edit.text(),
        dialog.api_key_edit.text(),
        dialog.model_edit.text(),
        dialog.tts_rate_spin.value(),
        dialog.poll_spin.value(),
    ) == ("https://api.deepseek.com/v1", "sk-stored", "deepseek-chat", 200, 2.5)


def test_dialog_save_calls_controller_save_config(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = ConfigDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.model_edit.setText("deepseek-reasoner")
    dialog.api_key_edit.setText("sk-new")

    dialog.save()

    saved = controller.save_config.call_args.args[0]  # type: ignore[attr-defined]
    assert (saved.llm_model, saved.llm_api_key) == ("deepseek-reasoner", "sk-new")


def test_dialog_save_failure_shows_critical_and_keeps_open(
    qtbot: object, mocker: MockerFixture
) -> None:
    controller = _controller(mocker)
    controller.save_config.side_effect = RuntimeError("save failed")  # type: ignore[attr-defined]
    critical = mocker.patch.object(QMessageBox, "critical")
    dialog = ConfigDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.save()

    assert critical.call_count == 1 and dialog.result() != QDialog.DialogCode.Accepted


def test_api_key_field_is_password_echo(qtbot: object, mocker: MockerFixture) -> None:
    controller = _controller(mocker)
    dialog = ConfigDialog(controller)  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Password
