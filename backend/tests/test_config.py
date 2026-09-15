import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accepts_postgresql_url_and_normalizes_driver() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql://soteops:soteops@127.0.0.1:5432/soteops",
        mock_integration_url="http://127.0.0.1:8001",
        llm_provider="fake",
    )
    assert settings.database_url == "postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops"
    assert settings.llm_provider == "fake"
    assert settings.cors_origin_list == ["http://127.0.0.1:3000"]


def test_settings_reject_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MOCK_INTEGRATION_URL", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "database_url" in str(exc_info.value)


def test_settings_reject_non_postgres_url() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            database_url="sqlite:///tmp.db",
            mock_integration_url="http://127.0.0.1:8001",
        )
    assert "PostgreSQL" in str(exc_info.value)


def test_settings_reject_unknown_llm_provider() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            database_url="postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
            mock_integration_url="http://127.0.0.1:8001",
            llm_provider="openai",  # type: ignore[arg-type]
        )


def test_settings_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            database_url="postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
            mock_integration_url="http://127.0.0.1:8001",
            paid_api_key="secret",  # type: ignore[call-arg]
        )
