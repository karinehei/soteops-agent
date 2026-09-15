from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_ready_reports_database_and_pgvector(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"] == {"database": "ok", "pgvector": "ok"}


def test_ready_returns_503_when_database_is_unreachable() -> None:
    settings = Settings(
        environment="test",
        log_level="INFO",
        database_url="postgresql+psycopg://soteops:soteops@127.0.0.1:65535/soteops",
        mock_integration_url="http://127.0.0.1:8001",
        llm_provider="fake",
    )
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "unavailable"
    assert response.json()["detail"]["checks"]["database"] == "error"
