from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import SessionDep, SettingsDep
from app.auth.deps import CsrfDep, CurrentUser
from app.models import AccessRequest, ApprovalDecision, AuditEvent, RequestStatus, User, UserRole
from app.schemas.requests import ApprovalAction, RequestWrite
from app.services.approvals import decide, start_review
from app.services.forwarding import current_submission, dispatch_request
from app.services.requests import (
    create_request,
    edit_request,
    get_request_for_user,
    list_requests,
    resubmit_request,
)

router = APIRouter(tags=["requests"])


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    revision: int
    extracted_fields: dict[str, Any]
    excerpts: dict[str, Any]
    missing_fields: list[Any]
    rule_violations: list[Any]
    explanation_text: str
    clarification_draft: str = ""
    source_references: list[Any]
    provider_metadata: dict[str, Any] = {}
    downstream_payload: dict[str, Any]
    policy_version: str
    payload_hash: str
    invalidated_at: datetime | None


class SubmissionOut(BaseModel):
    idempotency_key: str
    status: str
    attempt_count: int
    downstream_reference: str | None
    error_category: str | None
    payload_hash: str
    revision: int


class RequestOut(BaseModel):
    id: UUID
    owner_id: UUID
    employee_identifier: str | None
    employment_type: str | None
    job_role: str | None
    unit: str | None
    target_system: str | None
    requested_access_role: str | None
    start_date: date | None
    end_date: date | None
    original_text: str
    revision: int
    status: str
    current_proposal: ProposalOut | None
    current_submission: SubmissionOut | None = None
    created_at: datetime
    updated_at: datetime


class AuditOut(BaseModel):
    id: UUID
    event_type: str
    actor_id: UUID | None
    request_id: UUID | None
    correlation_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


def _status_value(value: RequestStatus | str) -> str:
    return value.value if isinstance(value, RequestStatus) else str(value)


def _to_out(request: AccessRequest, db: Session | None = None) -> RequestOut:
    proposal = request.current_proposal
    submission_out = None
    if db is not None:
        submission = current_submission(db, request.id)
        if submission is not None:
            submission_out = SubmissionOut(
                idempotency_key=submission.idempotency_key,
                status=str(getattr(submission.status, "value", submission.status)),
                attempt_count=submission.attempt_count,
                downstream_reference=submission.downstream_reference,
                error_category=submission.error_category,
                payload_hash=submission.payload_hash,
                revision=submission.revision,
            )
    return RequestOut(
        id=request.id,
        owner_id=request.owner_id,
        employee_identifier=request.employee_identifier,
        employment_type=request.employment_type,
        job_role=request.job_role,
        unit=request.unit,
        target_system=request.target_system,
        requested_access_role=request.requested_access_role,
        start_date=request.start_date,
        end_date=request.end_date,
        original_text=request.original_text,
        revision=request.revision,
        status=_status_value(request.status),
        current_proposal=ProposalOut.model_validate(proposal) if proposal is not None else None,
        current_submission=submission_out,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


def _reviewer(user: CurrentUser) -> User:
    if user.role != UserRole.REVIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only reviewers can access this resource",
        )
    return user


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_access_request(
    payload: RequestWrite,
    user: CurrentUser,
    db: SessionDep,
    _: CsrfDep,
) -> RequestOut:
    return _to_out(create_request(db, user, payload), db)


@router.get("/requests")
def list_access_requests(user: CurrentUser, db: SessionDep) -> list[RequestOut]:
    return [_to_out(item, db) for item in list_requests(db, user)]


@router.get("/review/queue")
def review_queue(user: CurrentUser, db: SessionDep) -> list[RequestOut]:
    _reviewer(user)
    items = [
        item
        for item in list_requests(db, user)
        if _status_value(item.status)
        in {RequestStatus.READY_FOR_REVIEW.value, RequestStatus.IN_REVIEW.value}
    ]
    return [_to_out(item, db) for item in items]


@router.get("/requests/{request_id}")
def get_access_request(request_id: UUID, user: CurrentUser, db: SessionDep) -> RequestOut:
    return _to_out(get_request_for_user(db, request_id, user), db)


@router.patch("/requests/{request_id}")
def patch_access_request(
    request_id: UUID,
    payload: RequestWrite,
    user: CurrentUser,
    db: SessionDep,
    _: CsrfDep,
) -> RequestOut:
    if user.role != UserRole.REQUESTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can edit a request"
        )
    request = get_request_for_user(db, request_id, user)
    return _to_out(edit_request(db, request, user, payload), db)


@router.post("/requests/{request_id}/resubmit")
def resubmit_access_request(
    request_id: UUID,
    user: CurrentUser,
    db: SessionDep,
    _: CsrfDep,
) -> RequestOut:
    if user.role != UserRole.REQUESTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can resubmit a request"
        )
    request = get_request_for_user(db, request_id, user)
    return _to_out(resubmit_request(db, request, user), db)


@router.post("/requests/{request_id}/review")
def review_access_request(
    request_id: UUID,
    user: CurrentUser,
    db: SessionDep,
    _: CsrfDep,
) -> RequestOut:
    return _to_out(start_review(db, request_id, user), db)


@router.post("/requests/{request_id}/approve")
def approve_request(
    request_id: UUID,
    payload: ApprovalAction,
    user: CurrentUser,
    db: SessionDep,
    _: CsrfDep,
) -> RequestOut:
    return _to_out(decide(db, request_id, user, payload, ApprovalDecision.APPROVE), db)


@router.post("/requests/{request_id}/reject")
def reject_request(
    request_id: UUID,
    payload: ApprovalAction,
    user: CurrentUser,
    db: SessionDep,
    _: CsrfDep,
) -> RequestOut:
    return _to_out(decide(db, request_id, user, payload, ApprovalDecision.REJECT), db)


@router.post("/requests/{request_id}/forward")
def forward_request(
    request_id: UUID,
    user: CurrentUser,
    db: SessionDep,
    settings: SettingsDep,
    _: CsrfDep,
) -> RequestOut:
    return _to_out(dispatch_request(db, request_id, user, settings=settings), db)


@router.get("/requests/{request_id}/audit")
def request_audit(request_id: UUID, user: CurrentUser, db: SessionDep) -> list[AuditOut]:
    request = get_request_for_user(db, request_id, user)
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.request_id == request.id)
        .order_by(AuditEvent.created_at.asc())
    ).all()
    return [
        AuditOut(
            id=event.id,
            event_type=event.event_type,
            actor_id=event.actor_id,
            request_id=event.request_id,
            correlation_id=event.correlation_id,
            metadata=event.metadata_json,
            created_at=event.created_at,
        )
        for event in events
    ]
