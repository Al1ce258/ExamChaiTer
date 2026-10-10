"""Environment-backed application settings."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SPLIT_PATTERNS: list[str] = [
    r"^\s*(\d{1,3})[.、)．]\s*",
    r"^\s*第\s*(\d{1,3})\s*题[.、:：]?\s*",
    r"^\s*\(\s*(\d{1,3})\s*\)\s*",
    r"^\s*[（(]\s*(\d{1,3})\s*[）)]\s*",
    r"^\s*【\s*(\d{1,3})\s*】",
    r"^\s*题目\s*(\d{1,3})\s*[:：]",
    r"^\s*\(?[一二三四五六七八九十]+\)?[.、．]\s*",
]


class Settings(BaseSettings):
    """Configuration loaded from EXAMCHAITER_* environment variables."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="EXAMCHAITER_",
        extra="ignore",
    )

    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_s: float = Field(default=60.0, gt=0.0)
    llm_max_retry: int = Field(default=2, ge=0)
    llm_vision_model: str = ""
    settle_ms: int = Field(default=120, ge=0)
    dedup_threshold: int = Field(default=5, ge=0)
    min_text_len: int = Field(default=5, ge=0)
    split_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_SPLIT_PATTERNS))
    clipboard: bool = False
    ocr_use_gpu: bool = False
    tts_interval_s: float = Field(default=3.0, gt=0.0)
    tts_enabled: bool = True
    tts_rate: int = Field(default=180, ge=0)
    log_level: str = "INFO"
    debug_dir: Path = Path("debug")
