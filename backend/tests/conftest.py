import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
)
os.environ.setdefault("MOCK_INTEGRATION_URL", "http://127.0.0.1:8001")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LLM_PROVIDER", "fake")

TEST_SETTINGS = Settings(
    environment="test",
    log_level="INFO",
    database_url=os.environ["DATABASE_URL"],
    mock_integration_url="http://127.0.0.1:8001",
    cors_origins="http://127.0.0.1:3000",
    llm_provider="fake",
    ollama_base_url=None,
    seed_file="seed/identities.json",
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(TEST_SETTINGS)) as test_client:
        yield test_client
