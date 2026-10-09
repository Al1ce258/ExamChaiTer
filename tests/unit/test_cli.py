"""Unit tests for the offline command-line entry point."""

import pytest

from examchaiter.__main__ import main


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


def test_without_command_prints_available_commands(capsys: pytest.CaptureFixture[str]) -> None:
    main([])

    assert "show-config" in capsys.readouterr().out


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
