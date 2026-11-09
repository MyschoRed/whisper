from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_keys: Annotated[list[str], NoDecode] = []
    whisper_url: str = "http://127.0.0.1:8081"
    model_name: str = "whisper-large-v3-turbo"
    default_language: str = "sk"
    max_upload_mb: int = 200
    request_timeout: float = 1800.0
    ffmpeg_bin: str = "ffmpeg"
    log_level: str = "info"

    @field_validator("api_keys", mode="before")
    @classmethod
    def split_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return [k.strip() for k in value.split(",") if k.strip()]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
