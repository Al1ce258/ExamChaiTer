"""Unit tests for the JSON/DPAPI-backed :class:`ConfigStore`."""

from __future__ import annotations

import base64
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from examchaiter.config import Settings
from examchaiter.errors import StorageError
from examchaiter.storage import config_store as config_store_module
from examchaiter.storage.config_store import AppConfig, ConfigStore


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("EXAMCHAITER_"):
            monkeypatch.delenv(key)
    monkeypatch.setattr(config_store_module, "_project_env_file", lambda: None)


@pytest.fixture
def fake_win32crypt(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    module = types.SimpleNamespace(
        CryptProtectData=lambda data, *args, **kwargs: b"enc:" + data,
        CryptUnprotectData=lambda blob, *args, **kwargs: ("ExamChaiTer", blob[4:]),
    )
    monkeypatch.setitem(sys.modules, "win32crypt", module)
    return module


@pytest.fixture
def no_win32crypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "win32crypt", None)


def _break_win32crypt(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise OSError("dpapi boom")

    monkeypatch.setitem(
        sys.modules,
        "win32crypt",
        types.SimpleNamespace(CryptProtectData=_boom, CryptUnprotectData=_boom),
    )


def test_default_base_dir_uses_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "x"
    monkeypatch.setenv("EXAMCHAITER_STORAGE_DIR", str(target))

    assert ConfigStore.default_base_dir() == target.resolve()


def test_default_base_dir_falls_back_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EXAMCHAITER_STORAGE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    assert ConfigStore.default_base_dir() == (tmp_path / ".examchaiter").resolve()


def test_default_base_dir_empty_env_var_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXAMCHAITER_STORAGE_DIR", "")
    monkeypatch.chdir(tmp_path)

    assert ConfigStore.default_base_dir() == (tmp_path / ".examchaiter").resolve()


def test_no_apdata_usage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXAMCHAITER_STORAGE_DIR", raising=False)
    monkeypatch.setenv("APPDATA", "C:/fake")
    monkeypatch.chdir(tmp_path)

    assert "fake" not in ConfigStore.default_base_dir().parts


def test_config_path_is_under_base_dir(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path)

    assert store.config_path == tmp_path / "config.json"


def test_constructor_creates_missing_base_dir(tmp_path: Path) -> None:
    base_dir = tmp_path / "nested" / "config"

    ConfigStore(base_dir)

    assert base_dir.is_dir()


def test_load_with_empty_dir_returns_defaults(tmp_path: Path, isolated_env: None) -> None:
    assert ConfigStore(tmp_path).load() == AppConfig()


def test_load_with_corrupt_json_returns_defaults(tmp_path: Path, isolated_env: None) -> None:
    (tmp_path / "config.json").write_text("{not valid json", encoding="utf-8")

    assert ConfigStore(tmp_path).load() == AppConfig()


def test_load_with_non_object_json_returns_defaults(tmp_path: Path, isolated_env: None) -> None:
    (tmp_path / "config.json").write_text("[1, 2, 3]", encoding="utf-8")

    assert ConfigStore(tmp_path).load() == AppConfig()


def test_load_from_env_maps_project_env_file(
    tmp_path: Path, isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "EXAMCHAITER_LLM_MODEL=deepseek-reasoner\nEXAMCHAITER_TTS_ENABLED=true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_store_module, "_project_env_file", lambda: env_file)

    config = ConfigStore(tmp_path / "cfg").load()

    assert (config.llm_model, config.tts_enabled) == ("deepseek-reasoner", True)


def test_save_then_load_round_trips_every_field(
    tmp_path: Path, isolated_env: None, fake_win32crypt: types.SimpleNamespace
) -> None:
    store = ConfigStore(tmp_path)
    config = AppConfig(
        llm_base_url="https://example.test/v1",
        llm_api_key="sk-roundtrip",
        llm_model="deepseek-reasoner",
        llm_vision_model="some-vision",
        llm_timeout=12.5,
        tts_enabled=True,
        tts_rate=200,
        tts_loop_interval=2.5,
        settle_ms=99,
        dedup_threshold=3,
        min_text_len=8,
        choice_with_text=True,
        clipboard=False,
        hotkey_answer="<ctrl>+a",
        hotkey_tts="<ctrl>+b",
        hotkey_quit="<ctrl>+c",
        log_level="DEBUG",
        auto_enabled=True,
        auto_poll_interval=2.0,
        auto_stable_frames=4,
        auto_speak_choice_repeat=6,
        auto_speak_fill_repeat=2,
        auto_speak_short_repeat=2,
        auto_speak_interval=4.0,
    )
    store.save(config)

    assert store.load() == config


def test_save_with_dpapi_stores_encrypted_field(
    tmp_path: Path, isolated_env: None, fake_win32crypt: types.SimpleNamespace
) -> None:
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_api_key="sk-secret"))

    raw = json.loads(store.config_path.read_text(encoding="utf-8"))

    assert "api_key" not in raw and "api_key_enc" in raw


def test_save_with_dpapi_does_not_store_plaintext_key(
    tmp_path: Path, isolated_env: None, fake_win32crypt: types.SimpleNamespace
) -> None:
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_api_key="sk-top-secret"))

    text = store.config_path.read_text(encoding="utf-8")

    assert "sk-top-secret" not in text


def test_load_decrypts_stored_api_key(
    tmp_path: Path, isolated_env: None, fake_win32crypt: types.SimpleNamespace
) -> None:
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_api_key="sk-decrypt"))

    assert ConfigStore(tmp_path).load().llm_api_key == "sk-decrypt"


def test_save_without_win32crypt_uses_plaintext(
    tmp_path: Path, isolated_env: None, no_win32crypt: None
) -> None:
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_api_key="sk-plain"))

    raw = json.loads(store.config_path.read_text(encoding="utf-8"))

    assert raw.get("api_key") == "sk-plain"


def test_save_without_win32crypt_warns_only_once(
    tmp_path: Path,
    isolated_env: None,
    no_win32crypt: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        config_store_module.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append(str(message)),
    )
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_api_key="sk-one"))
    store.save(AppConfig(llm_api_key="sk-two"))

    assert len(warnings) == 1


def test_load_with_encrypted_key_and_missing_win32crypt_returns_empty(
    tmp_path: Path, isolated_env: None, no_win32crypt: None
) -> None:
    token = base64.b64encode(b"enc:sk-x").decode("ascii")
    (tmp_path / "config.json").write_text(json.dumps({"api_key_enc": token}), encoding="utf-8")

    assert ConfigStore(tmp_path).load().llm_api_key == ""


def test_load_with_undecryptable_key_returns_empty(
    tmp_path: Path, isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _break_win32crypt(monkeypatch)
    token = base64.b64encode(b"enc:sk-x").decode("ascii")
    (tmp_path / "config.json").write_text(json.dumps({"api_key_enc": token}), encoding="utf-8")

    assert ConfigStore(tmp_path).load().llm_api_key == ""


def test_to_settings_before_load_returns_settings_instance(
    tmp_path: Path, isolated_env: None
) -> None:
    assert isinstance(ConfigStore(tmp_path).to_settings(), Settings)


def test_to_settings_maps_app_config_fields(tmp_path: Path, isolated_env: None) -> None:
    store = ConfigStore(tmp_path)
    store.save(
        AppConfig(
            llm_api_key="sk-settings",
            llm_model="deepseek-reasoner",
            llm_timeout=12.5,
            tts_enabled=True,
            tts_loop_interval=2.5,
            clipboard=False,
            min_text_len=7,
        )
    )
    settings = store.to_settings()

    assert (
        settings.llm_model,
        settings.llm_timeout_s,
        settings.tts_interval_s,
        settings.tts_enabled,
        settings.clipboard,
        settings.min_text_len,
    ) == ("deepseek-reasoner", 12.5, 2.5, True, False, 7)


def test_to_settings_sets_none_for_empty_api_key(tmp_path: Path, isolated_env: None) -> None:
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_api_key=""))

    assert store.to_settings().llm_api_key is None


def test_save_replace_failure_preserves_existing_file(
    tmp_path: Path,
    isolated_env: None,
    fake_win32crypt: types.SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ConfigStore(tmp_path)
    store.save(AppConfig(llm_model="original"))

    def _boom(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(StorageError):
        store.save(AppConfig(llm_model="updated"))

    assert ConfigStore(tmp_path).load().llm_model == "original"


def test_project_env_file_finds_dotenv_in_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("EXAMCHAITER_LLM_MODEL=x\n", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert config_store_module._project_env_file() == env_file
