from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Shared root .env also contains API/Compose keys; mock only reads its own fields.
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["local", "test", "ci"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


def load_settings() -> Settings:
    return Settings()
