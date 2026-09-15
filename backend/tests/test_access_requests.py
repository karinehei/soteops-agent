from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from app.core.config import Settings
from app.core.db import create_db_engine, create_session_factory
from app.main import create_app
from app.models import AccessRequest, ApprovalDecision, Proposal, RequestStatus, User
from app.schemas.requests import ApprovalAction, RequestWrite
from app.services.approvals import decide
from app.services.audit import ALLOWED_METADATA_KEYS, record_audit
from app.services.proposals import prepare_proposal
from app.services.requests import apply_write, create_request
from tests.conftest import (
    OPERATOR_EMAIL,
    REQUESTER_EMAIL,
    REVIEWER_EMAIL,
    SECOND_REQUESTER_EMAIL,
    SECOND_REVIEWER_EMAIL,
    TEST_SETTINGS,
    VALID_REQUEST,
    csrf_headers,
    login,
    seed_passwords,
)


def _logout(client: TestClient) -> None:
    response = client.post("/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 200, response.text


def _create(client: TestClient, payload: dict[str, object] | None = None) -> dict[str, object]:
    response = client.post("/requests", json=payload or VALID_REQUEST, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def _approval_body(request_payload: dict[str, object], **overrides: object) -> dict[str, object]:
    proposal = request_payload["current_proposal"]
    assert isinstance(proposal, dict)
    body: dict[str, object] = {
        "proposal_id": proposal["id"],
        "revision": request_payload["revision"],
        "payload_hash": proposal["payload_hash"],
        "policy_version": proposal["policy_version"],
        "comment": "ok",
    }
    body.update(overrides)
    return body


def _user(session: Session, email: str) -> User:
    user = session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def test_login_uses_httponly_session_cookie_not_bearer_token(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    me = domain_client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["identity_provider"] == "local-demo"
    assert "Entra" in body["note"]
    assert SESSION_COOKIE in domain_client.cookies
    assert CSRF_COOKIE in domain_client.cookies
    assert "access_token" not in body
    assert "token" not in body


def test_unauthenticated_request_is_rejected(domain_client: TestClient) -> None:
    response = domain_client.get("/requests")
    assert response.status_code == 401


def test_csrf_is_required_for_mutations(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    response = domain_client.post("/requests", json=VALID_REQUEST)
    assert response.status_code == 403


def test_requester_sees_only_own_requests(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    _logout(domain_client)
    login(domain_client, SECOND_REQUESTER_EMAIL)
    listed = domain_client.get("/requests")
    assert listed.status_code == 200
    assert listed.json() == []
    hidden = domain_client.get(f"/requests/{created['id']}")
    assert hidden.status_code == 404
    audit = domain_client.get(f"/requests/{created['id']}/audit")
    assert audit.status_code == 404


def test_requester_cannot_access_review_queue_or_approve(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    queue = domain_client.get("/review/queue")
    assert queue.status_code == 403
    approve = domain_client.post(
        f"/requests/{created['id']}/approve",
        json=_approval_body(created),
        headers=csrf_headers(domain_client),
    )
    assert approve.status_code == 403


def test_body_cannot_supply_owner_or_reviewer_identity(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    payload = dict(VALID_REQUEST)
    payload["owner_id"] = str(uuid4())
    payload["reviewer_id"] = str(uuid4())
    payload["actor_id"] = str(uuid4())
    response = domain_client.post("/requests", json=payload, headers=csrf_headers(domain_client))
    assert response.status_code == 422


def test_reviewer_queue_and_happy_path_approve(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    assert created["status"] == "ready_for_review"
    _logout(domain_client)
    login(domain_client, REVIEWER_EMAIL)
    queue = domain_client.get("/review/queue")
    assert queue.status_code == 200
    assert any(item["id"] == created["id"] for item in queue.json())
    reviewed = domain_client.post(
        f"/requests/{created['id']}/review", headers=csrf_headers(domain_client)
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "in_review"
    approved = domain_client.post(
        f"/requests/{created['id']}/approve",
        json=_approval_body(reviewed.json()),
        headers=csrf_headers(domain_client),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    audit = domain_client.get(f"/requests/{created['id']}/audit")
    types = {item["event_type"] for item in audit.json()}
    assert "request_created" in types
    assert "proposal_prepared" in types
    assert "review_approved" in types
    for event in audit.json():
        assert set(event["metadata"]) <= ALLOWED_METADATA_KEYS


def test_self_approval_is_rejected(domain_client: TestClient) -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            reviewer = _user(session, REVIEWER_EMAIL)
            payload = RequestWrite.model_validate(VALID_REQUEST)
            request = AccessRequest(
                owner_id=reviewer.id,
                original_text=payload.original_text,
                revision=1,
                status=RequestStatus.SUBMITTED,
            )
            session.add(request)
            session.flush()
            apply_write(request, payload)
            prepare_proposal(session, request, reviewer.id)
            session.commit()
            session.refresh(request)
            proposal = request.current_proposal
            assert proposal is not None
            request_id = request.id
            action = ApprovalAction(
                proposal_id=proposal.id,
                revision=request.revision,
                payload_hash=proposal.payload_hash,
                policy_version=proposal.policy_version,
            )
    finally:
        engine.dispose()

    login(domain_client, REVIEWER_EMAIL)
    response = domain_client.post(
        f"/requests/{request_id}/approve",
        json=action.model_dump(mode="json"),
        headers=csrf_headers(domain_client),
    )
    assert response.status_code == 403
    assert "Self-approval" in response.json()["detail"]


def test_invalid_transition_rejected_request_cannot_be_approved(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    _logout(domain_client)
    login(domain_client, REVIEWER_EMAIL)
    rejected = domain_client.post(
        f"/requests/{created['id']}/reject",
        json=_approval_body(created, comment="puutteellinen"),
        headers=csrf_headers(domain_client),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    again = domain_client.post(
        f"/requests/{created['id']}/approve",
        json=_approval_body(rejected.json()),
        headers=csrf_headers(domain_client),
    )
    assert again.status_code == 409


def test_edit_invalidates_previous_proposal_and_stale_approval(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    stale = _approval_body(created)
    updated_payload = dict(VALID_REQUEST)
    updated_payload["original_text"] = str(created["original_text"]) + " Päivitys."
    updated_payload["unit"] = "demo-osasto-2"
    edited = domain_client.patch(
        f"/requests/{created['id']}",
        json=updated_payload,
        headers=csrf_headers(domain_client),
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["revision"] == 2
    assert body["current_proposal"]["id"] != created["current_proposal"]["id"]
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            previous = session.get(Proposal, created["current_proposal"]["id"])
            assert previous is not None
            assert previous.invalidated_at is not None
    finally:
        engine.dispose()
    _logout(domain_client)
    login(domain_client, REVIEWER_EMAIL)
    stale_response = domain_client.post(
        f"/requests/{created['id']}/approve",
        json=stale,
        headers=csrf_headers(domain_client),
    )
    assert stale_response.status_code == 409


def test_policy_violation_cannot_be_approved(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    payload = dict(VALID_REQUEST)
    payload["requested_access_role"] = "tuotanto-superadmin"
    payload["original_text"] = str(payload["original_text"]) + " tuotanto-superadmin"
    created = _create(domain_client, payload)
    assert created["status"] == "needs_clarification"
    proposal = created["current_proposal"]
    assert isinstance(proposal, dict)
    assert any(item["code"] == "prohibited_role" for item in proposal["rule_violations"])
    _logout(domain_client)
    login(domain_client, REVIEWER_EMAIL)
    response = domain_client.post(
        f"/requests/{created['id']}/approve",
        json=_approval_body(created),
        headers=csrf_headers(domain_client),
    )
    assert response.status_code == 409


def test_resubmit_creates_new_revision(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    resubmitted = domain_client.post(
        f"/requests/{created['id']}/resubmit",
        headers=csrf_headers(domain_client),
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["revision"] == 2
    assert resubmitted.json()["current_proposal"]["id"] != created["current_proposal"]["id"]


def test_operator_cannot_approve(domain_client: TestClient) -> None:
    login(domain_client, REQUESTER_EMAIL)
    created = _create(domain_client)
    _logout(domain_client)
    login(domain_client, OPERATOR_EMAIL)
    response = domain_client.post(
        f"/requests/{created['id']}/approve",
        json=_approval_body(created),
        headers=csrf_headers(domain_client),
    )
    assert response.status_code == 403


def test_demo_auth_disabled_rejects_login() -> None:
    settings = Settings(
        environment="test",
        database_url=TEST_SETTINGS.database_url,
        mock_integration_url=TEST_SETTINGS.mock_integration_url,
        llm_provider="fake",
        demo_auth_enabled=False,
        session_secret="",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        token = client.get("/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/auth/login",
            json={"email": REQUESTER_EMAIL, "password": seed_passwords()[REQUESTER_EMAIL]},
            headers={CSRF_HEADER: token},
        )
        assert response.status_code == 403
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        engine.dispose()


def test_concurrent_approval_attempts_reject_the_loser(isolated_db: None) -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            requester = _user(session, REQUESTER_EMAIL)
            payload = RequestWrite.model_validate(VALID_REQUEST)
            request = create_request(session, requester, payload)
            request_id = request.id
            proposal = request.current_proposal
            assert proposal is not None
            action = ApprovalAction(
                proposal_id=proposal.id,
                revision=request.revision,
                payload_hash=proposal.payload_hash,
                policy_version=proposal.policy_version,
            )
            reviewer_ids = [
                _user(session, REVIEWER_EMAIL).id,
                _user(session, SECOND_REVIEWER_EMAIL).id,
            ]

        def _attempt(reviewer_id: object) -> int:
            worker = factory()
            try:
                reviewer = worker.get(User, reviewer_id)
                assert reviewer is not None
                decide(worker, request_id, reviewer, action, ApprovalDecision.APPROVE)
                return 200
            except HTTPException as exc:
                return exc.status_code
            finally:
                worker.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(_attempt, reviewer_ids))
        assert sorted(statuses) == [200, 409]
        with factory() as session:
            stored = session.get(AccessRequest, request_id)
            assert stored is not None
            assert stored.status in {RequestStatus.APPROVED, RequestStatus.APPROVED.value}
    finally:
        engine.dispose()


def test_audit_metadata_is_allowlisted(isolated_db: None) -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            event = record_audit(
                session,
                event_type="request_created",
                actor_id=None,
                request_id=None,
                metadata={"status": "submitted", "secret": "nope", "revision": 1},
            )
            session.commit()
            assert event.metadata_json == {"status": "submitted", "revision": 1}
            assert "secret" not in event.metadata_json
    finally:
        engine.dispose()
