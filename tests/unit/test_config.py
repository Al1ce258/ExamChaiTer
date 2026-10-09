"""Unit tests for environment-backed settings."""

import pytest
from pydantic import ValidationError

from examchaiter.config import Settings


def test_settings_without_api_key_uses_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)

    assert Settings(_env_file=None).llm_api_key is None


def test_settings_with_prefixed_api_key_reads_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMCHAITER_LLM_API_KEY", "sk-fake")

    settings = Settings(_env_file=None)

    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "sk-fake"


def test_settings_with_unprefixed_api_key_ignores_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXAMCHAITER_LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "sk-unprefixed")

    assert Settings(_env_file=None).llm_api_key is None


def test_settings_with_interval_override_parses_float(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMCHAITER_TTS_INTERVAL_S", "1.5")

    assert Settings(_env_file=None).tts_interval_s == 1.5


def test_settings_with_zero_interval_rejects_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMCHAITER_TTS_INTERVAL_S", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_json_dump_hides_secret_value() -> None:
    settings = Settings(_env_file=None, llm_api_key="sk-fake")

    assert settings.model_dump(mode="json")["llm_api_key"] == "**********"
