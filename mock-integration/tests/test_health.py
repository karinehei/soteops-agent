from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mock_integration.config import Settings
from mock_integration.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(environment="test", log_level="INFO")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "mock-integration"}


def test_ready_does_not_provision_accounts(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "stores_accounts": False}
