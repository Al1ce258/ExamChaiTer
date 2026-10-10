"""Persistent application configuration backed by a JSON file and DPAPI."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import SecretStr

from examchaiter.config import DEFAULT_SPLIT_PATTERNS, Settings
from examchaiter.errors import StorageError

STORAGE_DIR_ENV = "EXAMCHAITER_STORAGE_DIR"
DEFAULT_STORAGE_DIR_NAME = ".examchaiter"
CONFIG_FILENAME = "config.json"

# AppConfig field -> Settings field for the fields Settings already exposes.
_SETTINGS_FIELD_MAP: dict[str, str] = {
    "llm_base_url": "llm_base_url",
    "llm_api_key": "llm_api_key",
    "llm_model": "llm_model",
    "llm_vision_model": "llm_vision_model",
    "llm_timeout": "llm_timeout_s",
    "tts_enabled": "tts_enabled",
    "tts_rate": "tts_rate",
    "tts_loop_interval": "tts_interval_s",
    "settle_ms": "settle_ms",
    "dedup_threshold": "dedup_threshold",
    "min_text_len": "min_text_len",
    "split_patterns": "split_patterns",
    "clipboard": "clipboard",
    "log_level": "log_level",
}


@dataclass
class AppConfig:
    """User-facing configuration persisted on disk."""

    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_vision_model: str = ""
    llm_timeout: float = 30.0
    tts_enabled: bool = False
    tts_rate: int = 180
    tts_loop_interval: float = 3.0
    settle_ms: int = 150
    dedup_threshold: int = 5
    min_text_len: int = 20
    split_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_SPLIT_PATTERNS))
    ocr_upscale: float = 1.0
    choice_with_text: bool = False
    clipboard: bool = True
    hotkey_answer: str = "<ctrl>+<alt>+q"
    hotkey_tts: str = "<ctrl>+<alt>+s"
    hotkey_quit: str = "<ctrl>+<alt>+x"
    log_level: str = "INFO"
    # Phase 11 AutoPilot（预留字段，本 Phase 只存不读）
    auto_enabled: bool = False
    auto_poll_interval: float = 1.5
    auto_stable_frames: int = 2
    auto_speak_choice_repeat: int = 5
    auto_speak_multi_choice_repeat: int = 5
    auto_speak_fill_repeat: int = 3
    auto_speak_short_repeat: int = 1
    auto_speak_interval: float = 3.0


def _import_win32crypt() -> Any:
    """Import ``win32crypt`` lazily so non-Windows hosts degrade gracefully."""
    try:
        import win32crypt
    except ImportError:
        return None
    return win32crypt


def _project_env_file() -> Path | None:
    """Return the nearest project ``.env`` walking up from the current directory."""
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write ``payload`` atomically via a sibling tmp file and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StorageError(f"无法写入 {path.name}") from exc


def resolve_storage_dir() -> Path:
    """Resolve the local runtime data directory without touching legacy APPDATA data."""

    configured = os.environ.get(STORAGE_DIR_ENV, "").strip()
    root = Path(configured) if configured else Path.cwd() / DEFAULT_STORAGE_DIR_NAME
    return root.expanduser().resolve()


class ConfigStore:
    """Read and write :class:`AppConfig` under a base directory."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir is not None else self.default_base_dir()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._config_path = self._base_dir / CONFIG_FILENAME
        self._config: AppConfig | None = None
        self._warned_plaintext = False

    @staticmethod
    def default_base_dir() -> Path:
        return resolve_storage_dir()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> AppConfig:
        """Load config with priority ``config.json`` > project ``.env`` > defaults."""
        config = self._load_from_file()
        if config is None:
            config = self._load_from_env()
        self._config = config
        return config

    def save(self, cfg: AppConfig) -> None:
        """Persist ``cfg`` atomically, encrypting the API key when DPAPI is available."""
        payload: dict[str, Any] = {
            app_field.name: getattr(cfg, app_field.name)
            for app_field in fields(AppConfig)
            if app_field.name != "llm_api_key"
        }
        if cfg.llm_api_key:
            marker, value = self._write_api_key(cfg.llm_api_key)
            payload[marker] = value
        _atomic_write_json(self._config_path, payload)
        self._config = cfg

    def to_settings(self) -> Settings:
        """Build a :class:`Settings` instance from the current :class:`AppConfig`."""
        config = self._config if self._config is not None else self.load()
        values: dict[str, Any] = {}
        for app_field, settings_field in _SETTINGS_FIELD_MAP.items():
            value = getattr(config, app_field)
            if app_field == "llm_api_key":
                value = SecretStr(value) if value else None
            values[settings_field] = value
        return Settings(**values)

    def _load_from_file(self) -> AppConfig | None:
        if not self._config_path.exists():
            return None
        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("配置文件损坏，回退到环境配置: {}", exc)
            return None
        if not isinstance(raw, dict):
            logger.warning("配置文件格式非法，回退到环境配置")
            return None
        config = AppConfig()
        for app_field in fields(AppConfig):
            if app_field.name == "llm_api_key":
                continue
            if app_field.name in raw:
                setattr(config, app_field.name, raw[app_field.name])
        config.llm_api_key = self._read_api_key(raw)
        return config

    def _read_api_key(self, raw: dict[str, Any]) -> str:
        encrypted = raw.get("api_key_enc")
        if isinstance(encrypted, str) and encrypted:
            return self._decrypt_api_key(encrypted)
        plaintext = raw.get("api_key")
        return plaintext if isinstance(plaintext, str) else ""

    def _decrypt_api_key(self, token: str) -> str:
        win32crypt = _import_win32crypt()
        if win32crypt is None:
            logger.warning("win32crypt 不可用，无法解密已保存的 API Key")
            return ""
        try:
            blob = base64.b64decode(token)
            decrypted = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
            return bytes(decrypted[1]).decode("utf-8")
        except Exception as exc:
            logger.warning("API Key 解密失败，已忽略: {}", exc)
            return ""

    def _write_api_key(self, api_key: str) -> tuple[str, str]:
        win32crypt = _import_win32crypt()
        if win32crypt is not None:
            try:
                blob = win32crypt.CryptProtectData(
                    api_key.encode("utf-8"), "ExamChaiTer", None, None, None, 0
                )
                return "api_key_enc", base64.b64encode(blob).decode("ascii")
            except Exception as exc:
                self._warn_plaintext(f"API Key 加密失败，降级明文存储: {exc}")
        else:
            self._warn_plaintext("win32crypt 不可用，API Key 将以明文保存")
        return "api_key", api_key

    def _warn_plaintext(self, message: str) -> None:
        if not self._warned_plaintext:
            logger.warning(message)
            self._warned_plaintext = True

    def _load_from_env(self) -> AppConfig:
        try:
            overrides: dict[str, Any] = {"_env_file": _project_env_file()}
            env_settings = Settings(**overrides)
        except Exception as exc:
            logger.warning("读取 .env 失败，使用默认配置: {}", exc)
            return AppConfig()
        config = AppConfig()
        provided = env_settings.model_fields_set
        for app_field, settings_field in _SETTINGS_FIELD_MAP.items():
            if settings_field not in provided:
                continue
            value = getattr(env_settings, settings_field)
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            setattr(config, app_field, value)
        return config
