"""Environment-backed application settings."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    clipboard: bool = False
    ocr_use_gpu: bool = False
    tts_interval_s: float = Field(default=3.0, gt=0.0)
    tts_enabled: bool = True
    tts_rate: int = Field(default=180, ge=0)
    log_level: str = "INFO"
    debug_dir: Path = Path("debug")
