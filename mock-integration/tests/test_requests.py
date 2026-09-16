from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from mock_integration.config import Settings
from mock_integration.main import FAULT_HEADER, IDEMPOTENCY_HEADER, create_app
from mock_integration.schemas import DownstreamRequest
from mock_integration.store import UniqueStore, compute_payload_hash


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "employee_identifier": "EMP-1001",
        "target_system": "demo-hr-testi",
        "requested_access_role": "lukuoikeus",
        "start_date": "2026-10-01",
        "end_date": None,
        "revision": 1,
        "policy_version": "policy-v1",
        "payload_hash": "0" * 64,
    }
    body.update(overrides)
    hashed = compute_payload_hash(DownstreamRequest.model_validate(body))
    body["payload_hash"] = hashed
    return body


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


def test_post_requires_idempotency_key(client: TestClient) -> None:
    response = client.post("/requests", json=_payload())
    assert response.status_code == 422


def test_repeat_submission_returns_same_record(client: TestClient) -> None:
    headers = {IDEMPOTENCY_HEADER: "req-1:abc"}
    first = client.post("/requests", json=_payload(), headers=headers)
    second = client.post("/requests", json=_payload(), headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["record_id"] == second.json()["record_id"]
    assert first.json()["stores_accounts"] is False
    lookup = client.get("/requests", params={"idempotency_key": "req-1:abc"})
    assert lookup.status_code == 200
    assert lookup.json()["record_id"] == first.json()["record_id"]


def test_same_key_different_payload_is_rejected(client: TestClient) -> None:
    headers = {IDEMPOTENCY_HEADER: "req-2:abc"}
    first = client.post("/requests", json=_payload(), headers=headers)
    assert first.status_code == 201
    other = _payload(requested_access_role="kirjaaja", end_date="2026-11-01")
    conflict = client.post("/requests", json=other, headers=headers)
    assert conflict.status_code == 409
    lookup = client.get("/requests", params={"idempotency_key": "req-2:abc"})
    assert lookup.json()["record_id"] == first.json()["record_id"]


def test_fail_before_does_not_store(client: TestClient) -> None:
    headers = {IDEMPOTENCY_HEADER: "req-3:abc", FAULT_HEADER: "fail-before"}
    response = client.post("/requests", json=_payload(), headers=headers)
    assert response.status_code == 500
    missing = client.get("/requests", params={"idempotency_key": "req-3:abc"})
    assert missing.status_code == 404


def test_lost_response_still_stores_record(client: TestClient) -> None:
    headers = {IDEMPOTENCY_HEADER: "req-4:abc", FAULT_HEADER: "lost-response"}
    response = client.post("/requests", json=_payload(), headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    lookup = client.get("/requests", params={"idempotency_key": "req-4:abc"})
    assert lookup.status_code == 200
    assert lookup.json()["stores_accounts"] is False


def test_unavailable_does_not_store(client: TestClient) -> None:
    headers = {IDEMPOTENCY_HEADER: "req-5:abc", FAULT_HEADER: "unavailable"}
    response = client.post("/requests", json=_payload(), headers=headers)
    assert response.status_code == 503
    missing = client.get("/requests", params={"idempotency_key": "req-5:abc"})
    assert missing.status_code == 404


def test_strict_schema_rejects_unknown_fields(client: TestClient) -> None:
    payload = _payload()
    payload["account_password"] = "secret"
    response = client.post("/requests", json=payload, headers={IDEMPOTENCY_HEADER: "req-6:abc"})
    assert response.status_code == 422


def test_concurrent_puts_keep_one_record() -> None:
    store = UniqueStore()
    payload = DownstreamRequest.model_validate(_payload())

    def _put(_: int) -> str:
        record, _created = store.put("concurrent-key", payload)
        return record.record_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_put, range(8)))
    assert len(set(ids)) == 1
    assert store.count() == 1
