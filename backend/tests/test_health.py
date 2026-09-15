from uuid import UUID

from fastapi.testclient import TestClient

from app.core.logging import CORRELATION_HEADER


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_includes_server_generated_correlation_id(client: TestClient) -> None:
    response = client.get("/health")
    correlation_id = response.headers[CORRELATION_HEADER]
    UUID(correlation_id)
    second = client.get("/health")
    assert second.headers[CORRELATION_HEADER] != correlation_id


def test_health_ignores_client_supplied_correlation_id(client: TestClient) -> None:
    response = client.get("/health", headers={CORRELATION_HEADER: "client-supplied-id"})
    assert response.headers[CORRELATION_HEADER] != "client-supplied-id"
    UUID(response.headers[CORRELATION_HEADER])
