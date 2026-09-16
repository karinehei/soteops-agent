from typing import Literal
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEMO_ENVIRONMENTS = frozenset({"local", "test", "ci", "demo"})
ALLOWED_FORWARD_HOSTS = frozenset({"127.0.0.1", "localhost", "mock-integration", "::1"})


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
    embedding_provider: Literal["fake", "ollama"] = "fake"
    ollama_base_url: AnyHttpUrl | None = Field(default=None)
    ollama_llm_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    llm_timeout_seconds: float = 8.0
    llm_max_retries: int = 2
    retrieval_top_k: int = 4
    forward_timeout_seconds: float = 3.0
    forward_max_attempts: int = 3
    seed_file: str | None = Field(default=None, validation_alias="SOTEOPS_SEED_FILE")
    instructions_file: str | None = Field(
        default=None, validation_alias="SOTEOPS_INSTRUCTIONS_FILE"
    )
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

    @field_validator("mock_integration_url")
    @classmethod
    def validate_forward_destination(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        host = urlparse(str(value)).hostname
        if host not in ALLOWED_FORWARD_HOSTS:
            raise ValueError(
                "MOCK_INTEGRATION_URL host must be a configured local destination "
                "(127.0.0.1, localhost, ::1, or mock-integration)"
            )
        return value

    @model_validator(mode="after")
    def validate_demo_auth(self) -> "Settings":
        if self.demo_auth_enabled and self.environment not in DEMO_ENVIRONMENTS:
            raise ValueError("DEMO_AUTH_ENABLED is only allowed for local, demo, test or ci")
        if self.demo_auth_enabled and len(self.session_secret) < 16:
            raise ValueError(
                "SESSION_SECRET must be at least 16 characters when demo auth is enabled"
            )
        if self.llm_provider == "ollama" and self.ollama_base_url is None:
            raise ValueError("OLLAMA_BASE_URL is required when LLM_PROVIDER=ollama")
        if self.embedding_provider == "ollama" and self.ollama_base_url is None:
            raise ValueError("OLLAMA_BASE_URL is required when EMBEDDING_PROVIDER=ollama")
        if self.llm_max_retries < 0:
            raise ValueError("LLM_MAX_RETRIES must be >= 0")
        if self.retrieval_top_k < 1:
            raise ValueError("RETRIEVAL_TOP_K must be >= 1")
        if self.forward_max_attempts < 1:
            raise ValueError("FORWARD_MAX_ATTEMPTS must be >= 1")
        if self.forward_timeout_seconds <= 0:
            raise ValueError("FORWARD_TIMEOUT_SECONDS must be > 0")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


def load_settings() -> Settings:
    return Settings()
