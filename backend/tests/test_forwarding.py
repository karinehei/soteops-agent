from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import create_db_engine, create_session_factory
from app.integrations.downstream import (
    DownstreamOutcome,
    DownstreamResult,
    _interpret_write,
    outbound_payload,
)
from app.models import (
    AccessRequest,
    ApprovalDecision,
    AuditEvent,
    RequestStatus,
    Submission,
    SubmissionStatus,
    User,
)
from app.rules.hashing import payload_hash
from app.rules.transitions import as_status
from app.schemas.requests import ApprovalAction, RequestWrite
from app.services.approvals import decide
from app.services.audit import ALLOWED_METADATA_KEYS
from app.services.forwarding import dispatch_request, dispatch_submission, recover_stale_in_flight
from app.services.requests import create_request
from mock_integration.config import Settings as MockSettings
from mock_integration.main import create_app as create_mock_app
from mock_integration.schemas import DownstreamRequest
from mock_integration.store import UniqueStore, compute_payload_hash
from tests.conftest import (
    OPERATOR_EMAIL,
    REQUESTER_EMAIL,
    REVIEWER_EMAIL,
    TEST_SETTINGS,
    VALID_REQUEST,
    csrf_headers,
    login,
)


class MockAppClient:
    def __init__(self, client: TestClient) -> None:
        self._client = client
        self._lock = Lock()
        self.post_calls = 0

    def post_request(
        self,
        idempotency_key: str,
        payload: dict[str, object],
        *,
        fault: str | None = None,
    ) -> DownstreamResult:
        with self._lock:
            self.post_calls += 1
            headers = {"Idempotency-Key": idempotency_key}
            if fault:
                headers["X-Mock-Fault"] = fault
            response = self._client.post("/requests", json=payload, headers=headers)
        mapped = httpx.Response(response.status_code, content=response.content)
        return _interpret_write(mapped, expected_hash=str(payload.get("payload_hash", "")))

    def get_request(self, idempotency_key: str) -> DownstreamResult:
        with self._lock:
            response = self._client.get("/requests", params={"idempotency_key": idempotency_key})
        if response.status_code == 404:
            return DownstreamResult(outcome=DownstreamOutcome.MISSING, status_code=404)
        mapped = httpx.Response(response.status_code, content=response.content)
        return _interpret_write(mapped, expected_hash="")


class TimeoutAfterStore(MockAppClient):
    def post_request(
        self,
        idempotency_key: str,
        payload: dict[str, object],
        *,
        fault: str | None = None,
    ) -> DownstreamResult:
        super().post_request(idempotency_key, payload, fault=fault)
        return DownstreamResult(outcome=DownstreamOutcome.UNKNOWN, error_category="timeout")


class AlwaysFailClient:
    def post_request(
        self,
        idempotency_key: str,
        payload: dict[str, object],
        *,
        fault: str | None = None,
    ) -> DownstreamResult:
        return DownstreamResult(outcome=DownstreamOutcome.FAILED, error_category="downstream_5xx")

    def get_request(self, idempotency_key: str) -> DownstreamResult:
        return DownstreamResult(outcome=DownstreamOutcome.MISSING, status_code=404)


@contextmanager
def mock_downstream() -> Iterator[tuple[TestClient, MockAppClient]]:
    app = create_mock_app(MockSettings(environment="test", log_level="INFO"))
    with TestClient(app) as starlette:
        yield starlette, MockAppClient(starlette)


def _engine_session() -> tuple[object, object]:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    return engine, factory()


def _user(session: object, email: str) -> User:
    user = session.scalar(select(User).where(User.email == email))  # type: ignore[attr-defined]
    assert user is not None
    return user


def _approve(session: object, request: AccessRequest) -> AccessRequest:
    reviewer = _user(session, REVIEWER_EMAIL)
    proposal = request.current_proposal
    assert proposal is not None
    return decide(
        session,  # type: ignore[arg-type]
        request.id,
        reviewer,
        ApprovalAction(
            proposal_id=proposal.id,
            revision=request.revision,
            payload_hash=proposal.payload_hash,
            policy_version=proposal.policy_version,
        ),
        ApprovalDecision.APPROVE,
    )


def _prepared_request(session: object) -> AccessRequest:
    requester = _user(session, REQUESTER_EMAIL)
    return create_request(
        session,  # type: ignore[arg-type]
        requester,
        RequestWrite.model_validate(VALID_REQUEST),
    )


def test_forward_without_approval_is_blocked(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = domain_client.post(
        "/requests", json=VALID_REQUEST, headers=csrf_headers(domain_client)
    )
    assert created.status_code == 201
    request_id = created.json()["id"]
    domain_client.post("/auth/logout", headers=csrf_headers(domain_client))
    login(domain_client, REVIEWER_EMAIL)
    forwarded = domain_client.post(
        f"/requests/{request_id}/forward", headers=csrf_headers(domain_client)
    )
    assert forwarded.status_code == 409


def test_requester_cannot_forward(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = domain_client.post(
        "/requests", json=VALID_REQUEST, headers=csrf_headers(domain_client)
    )
    forwarded = domain_client.post(
        f"/requests/{created.json()['id']}/forward", headers=csrf_headers(domain_client)
    )
    assert forwarded.status_code == 403


def test_rejected_proposal_cannot_submit(isolated_db: None) -> None:
    engine, session = _engine_session()
    try:
        request = _prepared_request(session)
        reviewer = _user(session, REVIEWER_EMAIL)
        proposal = request.current_proposal
        assert proposal is not None
        decide(
            session,
            request.id,
            reviewer,
            ApprovalAction(
                proposal_id=proposal.id,
                revision=request.revision,
                payload_hash=proposal.payload_hash,
                policy_version=proposal.policy_version,
            ),
            ApprovalDecision.REJECT,
        )
        operator = _user(session, OPERATOR_EMAIL)
        with pytest.raises(HTTPException) as exc:
            dispatch_request(session, request.id, operator, settings=TEST_SETTINGS)
        assert exc.value.status_code == 409
        assert (session.scalar(select(func.count()).select_from(Submission)) or 0) == 0
    finally:
        session.close()
        engine.dispose()


def test_pending_submission_blocks_edits(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = domain_client.post(
        "/requests", json=VALID_REQUEST, headers=csrf_headers(domain_client)
    )
    body = created.json()
    domain_client.post("/auth/logout", headers=csrf_headers(domain_client))
    login(domain_client, REVIEWER_EMAIL)
    approved = domain_client.post(
        f"/requests/{body['id']}/approve",
        json={
            "proposal_id": body["current_proposal"]["id"],
            "revision": body["revision"],
            "payload_hash": body["current_proposal"]["payload_hash"],
            "policy_version": body["current_proposal"]["policy_version"],
        },
        headers=csrf_headers(domain_client),
    )
    assert approved.status_code == 200
    assert approved.json()["current_submission"]["status"] == "pending"
    domain_client.post("/auth/logout", headers=csrf_headers(domain_client))
    login(domain_client, REQUESTER_EMAIL)
    edited = domain_client.patch(
        f"/requests/{body['id']}", json=VALID_REQUEST, headers=csrf_headers(domain_client)
    )
    assert edited.status_code == 409


def test_successful_forward_creates_one_mock_record(isolated_db: None) -> None:
    engine, session = _engine_session()
    with mock_downstream() as (starlette, client):
        try:
            request = _approve(session, _prepared_request(session))
            operator = _user(session, OPERATOR_EMAIL)
            updated = dispatch_request(
                session, request.id, operator, settings=TEST_SETTINGS, client=client
            )
            assert as_status(updated.status) == RequestStatus.FORWARDED
            submission = session.scalar(
                select(Submission).where(Submission.request_id == request.id)
            )
            assert submission is not None
            assert submission.status in {SubmissionStatus.ACCEPTED, "accepted"}
            assert submission.downstream_reference
            lookup = starlette.get(
                "/requests", params={"idempotency_key": submission.idempotency_key}
            )
            assert lookup.status_code == 200
            assert lookup.json()["stores_accounts"] is False
            events = list(
                session.scalars(select(AuditEvent).where(AuditEvent.request_id == request.id)).all()
            )
            types = [event.event_type for event in events]
            assert "submission_scheduled" in types
            assert "submission_attempt" in types
            assert "submission_accepted" in types
            assert types.index("submission_scheduled") < types.index("review_approved")
            assert types.index("submission_attempt") < types.index("submission_accepted")
            for event in events:
                assert set(event.metadata_json) <= ALLOWED_METADATA_KEYS
                assert "payload" not in event.metadata_json
                assert "password" not in event.metadata_json
        finally:
            session.close()
            engine.dispose()


def test_stale_proposal_cannot_submit(isolated_db: None) -> None:
    engine, session = _engine_session()
    with mock_downstream() as (_starlette, client):
        try:
            request = _approve(session, _prepared_request(session))
            submission = session.scalar(
                select(Submission).where(Submission.request_id == request.id)
            )
            assert submission is not None
            submission.payload_hash = "0" * 64
            session.commit()
            operator = _user(session, OPERATOR_EMAIL)
            with pytest.raises(HTTPException) as exc:
                dispatch_request(
                    session, request.id, operator, settings=TEST_SETTINGS, client=client
                )
            assert exc.value.status_code == 409
        finally:
            session.close()
            engine.dispose()


def test_commit_then_timeout_is_reconciled(isolated_db: None) -> None:
    engine, session = _engine_session()
    with mock_downstream() as (starlette, _inner):
        client = TimeoutAfterStore(starlette)
        try:
            request = _approve(session, _prepared_request(session))
            operator = _user(session, OPERATOR_EMAIL)
            updated = dispatch_request(
                session, request.id, operator, settings=TEST_SETTINGS, client=client
            )
            submission = session.scalar(
                select(Submission).where(Submission.request_id == request.id)
            )
            assert submission is not None
            assert submission.idempotency_key == f"{request.id}:{submission.payload_hash}"
            assert as_status(updated.status) == RequestStatus.FORWARDED
            assert submission.status in {SubmissionStatus.ACCEPTED, "accepted"}
            assert client.post_calls == 1
        finally:
            session.close()
            engine.dispose()


def test_process_restart_preserves_pending_work(isolated_db: None) -> None:
    engine, session = _engine_session()
    with mock_downstream() as (starlette, client):
        try:
            request = _approve(session, _prepared_request(session))
            request_id = request.id
            proposal = request.current_proposal
            assert proposal is not None
            payload_hash = proposal.payload_hash
            submission = session.scalar(
                select(Submission).where(Submission.request_id == request_id)
            )
            assert submission is not None
            assert submission.status in {SubmissionStatus.PENDING, "pending"}
            session.close()
            factory = create_session_factory(engine)
            with factory() as restarted:
                operator = _user(restarted, OPERATOR_EMAIL)
                dispatch_request(
                    restarted, request_id, operator, settings=TEST_SETTINGS, client=client
                )
                stored = restarted.get(AccessRequest, request_id)
                assert stored is not None
                assert as_status(stored.status) == RequestStatus.FORWARDED
            lookup = starlette.get(
                "/requests",
                params={"idempotency_key": f"{request_id}:{payload_hash}"},
            )
            assert lookup.status_code == 200
        finally:
            engine.dispose()


def test_concurrent_dispatchers_do_not_duplicate(isolated_db: None) -> None:
    engine, session = _engine_session()
    factory = create_session_factory(engine)
    with mock_downstream() as (starlette, client):
        try:
            request = _approve(session, _prepared_request(session))
            request_id = request.id
            proposal = request.current_proposal
            assert proposal is not None
            key = f"{request_id}:{proposal.payload_hash}"
            submission = session.scalar(
                select(Submission).where(Submission.request_id == request.id)
            )
            assert submission is not None
            submission_id = submission.id
            operator_id = _user(session, OPERATOR_EMAIL).id
            session.close()

            def _run(_: int) -> str:
                worker = factory()
                try:
                    dispatch_submission(
                        worker, submission_id, operator_id, settings=TEST_SETTINGS, client=client
                    )
                    row = worker.get(Submission, submission_id)
                    assert row is not None
                    return str(row.downstream_reference)
                finally:
                    worker.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                references = list(pool.map(_run, [1, 2]))
            assert references[0] == references[1]
            assert references[0] != "None"
            lookup = starlette.get("/requests", params={"idempotency_key": key})
            assert lookup.status_code == 200
        finally:
            engine.dispose()


def test_same_key_different_payload_is_rejected_by_mock() -> None:
    store = UniqueStore()
    first = {
        "employee_identifier": "EMP-1001",
        "target_system": "demo-hr-testi",
        "requested_access_role": "lukuoikeus",
        "start_date": "2026-10-01",
        "end_date": None,
        "revision": 1,
        "policy_version": "policy-v1",
    }
    first_hash = payload_hash(first)
    record, created = store.put(
        "req-x:hash",
        DownstreamRequest.model_validate({**first, "payload_hash": first_hash}),
    )
    assert created is True
    other = {**first, "requested_access_role": "kirjaaja"}
    with pytest.raises(KeyError):
        store.put(
            "req-x:hash",
            DownstreamRequest.model_validate({**other, "payload_hash": payload_hash(other)}),
        )
    replay, created_again = store.put(
        "req-x:hash",
        DownstreamRequest.model_validate({**first, "payload_hash": first_hash}),
    )
    assert created_again is False
    assert replay.record_id == record.record_id


def test_outbound_payload_hash_matches_mock_store() -> None:
    downstream = {
        "employee_identifier": "EMP-1001",
        "target_system": "demo-hr-testi",
        "requested_access_role": "lukuoikeus",
        "start_date": "2026-10-01",
        "end_date": None,
        "revision": 1,
        "policy_version": "policy-v1",
    }
    hashed = payload_hash(downstream)
    body = outbound_payload(downstream, hashed)
    parsed = DownstreamRequest.model_validate(body)
    assert compute_payload_hash(parsed) == hashed


def test_retries_stop_at_documented_limit(isolated_db: None) -> None:
    engine, session = _engine_session()
    limited = TEST_SETTINGS.model_copy(update={"forward_max_attempts": 2})
    try:
        request = _approve(session, _prepared_request(session))
        operator = _user(session, OPERATOR_EMAIL)
        dispatch_request(session, request.id, operator, settings=limited, client=AlwaysFailClient())
        dispatch_request(session, request.id, operator, settings=limited, client=AlwaysFailClient())
        submission = session.scalar(select(Submission).where(Submission.request_id == request.id))
        assert submission is not None
        assert submission.status in {SubmissionStatus.EXHAUSTED, "exhausted"}
        assert submission.attempt_count == 2
        with pytest.raises(HTTPException) as exc:
            dispatch_request(
                session, request.id, operator, settings=limited, client=AlwaysFailClient()
            )
        assert exc.value.status_code == 409
        assert "FORWARD_MAX_ATTEMPTS=2" in str(exc.value.detail)
    finally:
        session.close()
        engine.dispose()


def test_stale_in_flight_is_recovered_as_unknown(isolated_db: None) -> None:
    engine, session = _engine_session()
    try:
        request = _approve(session, _prepared_request(session))
        submission = session.scalar(select(Submission).where(Submission.request_id == request.id))
        assert submission is not None
        submission.status = SubmissionStatus.IN_FLIGHT
        submission.claimed_at = datetime.now(UTC) - timedelta(minutes=5)
        submission.attempt_count = 1
        session.commit()
        recovered = recover_stale_in_flight(session, TEST_SETTINGS)
        session.commit()
        session.refresh(submission)
        assert recovered == 1
        assert submission.status in {SubmissionStatus.UNKNOWN, "unknown"}
    finally:
        session.close()
        engine.dispose()


def test_live_mock_health_in_ci() -> None:
    url = str(TEST_SETTINGS.mock_integration_url).rstrip("/") + "/health"
    try:
        response = httpx.get(url, timeout=0.5)
    except httpx.HTTPError:
        pytest.skip("mock integration is not listening")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "mock-integration"


def test_live_mock_idempotency_in_ci() -> None:
    base = str(TEST_SETTINGS.mock_integration_url).rstrip("/")
    downstream = {
        "employee_identifier": "EMP-1001",
        "target_system": "demo-hr-testi",
        "requested_access_role": "lukuoikeus",
        "start_date": "2026-10-01",
        "end_date": None,
        "revision": 1,
        "policy_version": "policy-v1",
    }
    body = outbound_payload(downstream, payload_hash(downstream))
    headers = {"Idempotency-Key": f"ci-live:{uuid4()}"}
    try:
        first = httpx.post(f"{base}/requests", json=body, headers=headers, timeout=0.5)
    except httpx.HTTPError:
        pytest.skip("mock integration is not listening")
    second = httpx.post(f"{base}/requests", json=body, headers=headers, timeout=0.5)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["record_id"] == second.json()["record_id"]
    assert first.json()["stores_accounts"] is False
    lookup = httpx.get(
        f"{base}/requests",
        params={"idempotency_key": headers["Idempotency-Key"]},
        timeout=0.5,
    )
    assert lookup.status_code == 200
    assert lookup.json()["record_id"] == first.json()["record_id"]
