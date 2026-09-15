from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEMO_ENVIRONMENTS = frozenset({"local", "test", "ci", "demo"})


class Settings(BaseSettings):
    """Validated runtime settings. Unknown fields are rejected."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=False,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "ci", "demo"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str
    mock_integration_url: AnyHttpUrl
    cors_origins: str = "http://127.0.0.1:3000"
    llm_provider: Literal["fake", "ollama"] = "fake"
    ollama_base_url: AnyHttpUrl | None = Field(default=None)
    seed_file: str | None = Field(default=None, validation_alias="SOTEOPS_SEED_FILE")
    demo_auth_enabled: bool = False
    session_secret: str = ""
    session_ttl_hours: int = 12
    cookie_secure: bool = False
    policy_file: str | None = None

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        allowed_prefixes = ("postgresql://", "postgresql+psycopg://")
        if not value.startswith(allowed_prefixes):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL using postgresql:// or postgresql+psycopg://"
            )
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def validate_demo_auth(self) -> "Settings":
        if self.demo_auth_enabled and self.environment not in DEMO_ENVIRONMENTS:
            raise ValueError("DEMO_AUTH_ENABLED is only allowed for local, demo, test or ci")
        if self.demo_auth_enabled and len(self.session_secret) < 16:
            raise ValueError(
                "SESSION_SECRET must be at least 16 characters when demo auth is enabled"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def load_settings() -> Settings:
    return Settings()
