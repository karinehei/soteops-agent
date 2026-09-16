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
    # Compose-only keys may live in the same .env; the API uses DATABASE_URL.
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    postgres_host_port: int | None = None
    mock_integration_url: AnyHttpUrl
    cors_origins: str = "http://127.0.0.1:3000"
    llm_provider: Literal["fake", "ollama", "azure_openai"] = "fake"
    embedding_provider: Literal["fake", "ollama", "azure_openai"] = "fake"
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
    # Azure OpenAI — opt-in only. Managed identity is not implemented in this slice.
    azure_openai_enabled: bool = False
    azure_openai_endpoint: AnyHttpUrl | None = None
    azure_openai_api_key: str | None = None
    azure_openai_chat_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None
    azure_openai_embedding_dimensions: int | None = None
    azure_openai_max_completion_tokens: int = 2048

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
        azure_selected = (
            self.llm_provider == "azure_openai" or self.embedding_provider == "azure_openai"
        )
        if azure_selected and not self.azure_openai_enabled:
            raise ValueError(
                "AZURE_OPENAI_ENABLED=true is required when LLM_PROVIDER or "
                "EMBEDDING_PROVIDER is azure_openai (no silent fallback)"
            )
        if self.azure_openai_enabled or azure_selected:
            if self.azure_openai_endpoint is None:
                raise ValueError("AZURE_OPENAI_ENDPOINT is required when Azure OpenAI is enabled")
            if not self.azure_openai_api_key:
                raise ValueError("AZURE_OPENAI_API_KEY is required when Azure OpenAI is enabled")
            if self.llm_provider == "azure_openai" and not self.azure_openai_chat_deployment:
                raise ValueError(
                    "AZURE_OPENAI_CHAT_DEPLOYMENT is required when LLM_PROVIDER=azure_openai"
                )
            if (
                self.embedding_provider == "azure_openai"
                and not self.azure_openai_embedding_deployment
            ):
                raise ValueError(
                    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required when "
                    "EMBEDDING_PROVIDER=azure_openai"
                )
        if (
            self.azure_openai_embedding_dimensions is not None
            and self.azure_openai_embedding_dimensions < 1
        ):
            raise ValueError("AZURE_OPENAI_EMBEDDING_DIMENSIONS must be >= 1")
        if self.azure_openai_max_completion_tokens < 1:
            raise ValueError("AZURE_OPENAI_MAX_COMPLETION_TOKENS must be >= 1")
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
