from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    secret_key: str = Field(
        default="dev-insecure-secret-key-change-me-32bytes!",
        min_length=32,
    )
    database_url: str = "sqlite:///./data.sqlite"
    voices_dir: str = "./voices"

    log_level: str = "INFO"
    access_token_ttl_days: int = 365
    pairing_code_ttl_seconds: int = 600
    max_voice_duration_seconds: int = 60

    pairing_code_length: int = 6
    token_bytes: int = 32

    @property
    def voices_path(self) -> Path:
        return Path(self.voices_dir).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
