"""Unit tests for the offline command-line entry point."""

import sys

import pytest
from pytest_mock import MockerFixture

from examchaiter.__main__ import main
from examchaiter.config import Settings


@pytest.fixture(autouse=True)
def _isolate_cli_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "examchaiter.__main__.Settings",
        lambda: Settings(_env_file=None),
    )


def test_version_option_exits_with_success() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0


def test_version_option_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])

    assert capsys.readouterr().out.strip() == "examchaiter 0.1.0"


def test_show_config_command_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)

    assert main(["show-config"]) == 0


def test_show_config_command_hides_real_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXAMCHAITER_LLM_API_KEY", "sk-real-secret")

    main(["show-config"])

    assert "sk-real-secret" not in capsys.readouterr().out


def test_show_config_command_masks_configured_api_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXAMCHAITER_LLM_API_KEY", "sk-real-secret")

    main(["show-config"])

    assert "llm_api_key=sk-***" in capsys.readouterr().out


def test_show_config_command_includes_default_model(capsys: pytest.CaptureFixture[str]) -> None:
    main(["show-config"])

    assert "llm_model=gpt-4o-mini" in capsys.readouterr().out


def test_help_flag_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0 and "show-config" in capsys.readouterr().out


def test_no_args_launches_gui(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["examchaiter"])
    run_gui = mocker.patch("examchaiter.__main__._run_gui", return_value=0)

    result = main()

    assert (
        result == 0 and run_gui.call_args == mocker.call(fake=False) and not capsys.readouterr().out
    )


def test_ask_command_without_real_prints_choice(capsys: pytest.CaptureFixture[str]) -> None:
    main(["ask", "1+1=?"])

    assert capsys.readouterr().out == "qtype=choice\ncontent=B\n"


def test_ask_command_with_real_without_key_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main(["ask", "1+1=?", "--real"])

    assert exc_info.value.code != 0


def test_answer_command_without_real_prints_multi_question_display(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["answer", "--title", "任意"])

    assert capsys.readouterr().out == "1. 答案：B\n2. 答案：C\n3. 答案：D\n"


def test_speak_command_without_real_prints_spoken_text(capsys: pytest.CaptureFixture[str]) -> None:
    main(["speak", "测试", "--loops", "2", "--interval", "0.01"])

    assert capsys.readouterr().out == "spoken=['测试', '测试']\n"


def test_run_dry_run_prints_hotkey_bindings(capsys: pytest.CaptureFixture[str]) -> None:
    main(["run", "--dry-run"])

    assert "<ctrl>+<alt>+q" in capsys.readouterr().out


def test_gui_fake_command_prints_ok(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["gui", "--fake"])

    assert result == 0 and "gui-ok" in capsys.readouterr().out


def test_list_windows_command_smoke(mocker: MockerFixture) -> None:
    mocker.patch("examchaiter.capture.window.list_windows", return_value=[])

    assert main(["list-windows", "--filter", ".*"]) == 0


def test_ocr_self_test_command_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    main(["ocr-self-test"])

    assert "第一行 题目示例" in capsys.readouterr().out


def test_ask_real_without_key_writes_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        main(["ask", "1+1=?", "--real"])

    assert "EXAMCHAITER_LLM_API_KEY" in capsys.readouterr().err


def test_answer_real_with_missing_window_exits_nonzero(mocker: MockerFixture) -> None:
    mocker.patch(
        "examchaiter.__main__.Settings",
        return_value=Settings(_env_file=None, llm_api_key="sk-test"),
    )
    mocker.patch("examchaiter.capture.window.find_window", return_value=None)

    assert main(["answer", "--title", "missing", "--real"]) != 0


def test_speak_real_with_import_failure_exits_nonzero(mocker: MockerFixture) -> None:
    mocker.patch(
        "examchaiter.tts.speaker.importlib.import_module",
        side_effect=ImportError("pyttsx3 unavailable"),
    )

    assert main(["speak", "text", "--real"]) != 0


def test_autopilot_dry_run_command_reports_answers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["autopilot-dry-run", "--frames", "5", "--session", "smoke"])

    out = capsys.readouterr().out
    assert (
        result,
        "on_answer count: 2" in out,
        "from_cache: fresh=1 cached=1" in out,
    ) == (0, True, True)
