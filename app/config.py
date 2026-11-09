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
    # None = automaticky: vypnuté pre "turbo" modely, ktoré preklad nepodporujú
    translations_enabled: bool | None = None

    @field_validator("api_keys", mode="before")
    @classmethod
    def split_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return [k.strip() for k in value.split(",") if k.strip()]
        return value

    @field_validator("translations_enabled", mode="before")
    @classmethod
    def empty_is_auto(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() in ("", "auto"):
            return None
        return value

    @property
    def translations_supported(self) -> bool:
        if self.translations_enabled is not None:
            return self.translations_enabled
        return "turbo" not in self.model_name.lower()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
