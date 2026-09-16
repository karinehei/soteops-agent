from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import AccessRequest, RequestStatus, User, UserRole
from app.rules.transitions import (
    EDITABLE_STATUSES,
    InvalidTransitionError,
    as_status,
    ensure_transition,
)
from app.schemas.requests import RequestWrite
from app.services.audit import record_audit
from app.services.forwarding import submission_blocks_edits
from app.services.proposals import prepare_proposal


def apply_write(request: AccessRequest, payload: RequestWrite) -> None:
    request.employee_identifier = payload.employee_identifier
    request.employment_type = payload.employment_type
    request.job_role = payload.job_role
    request.unit = payload.unit
    request.target_system = payload.target_system
    request.requested_access_role = payload.requested_access_role
    request.start_date = payload.start_date
    request.end_date = payload.end_date
    request.original_text = payload.original_text


def create_request(session: Session, owner: User, payload: RequestWrite) -> AccessRequest:
    if owner.role != UserRole.REQUESTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only requesters can create requests"
        )
    request = AccessRequest(
        id=uuid4(),
        owner_id=owner.id,
        original_text=payload.original_text,
        revision=1,
        status=RequestStatus.SUBMITTED,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    apply_write(request, payload)
    session.add(request)
    session.flush()
    record_audit(
        session,
        event_type="request_created",
        actor_id=owner.id,
        request_id=request.id,
        metadata={"status": RequestStatus.SUBMITTED.value, "revision": 1},
    )
    try:
        prepare_proposal(session, request, owner.id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    session.commit()
    return reload_request(session, request.id)


def edit_request(
    session: Session, request: AccessRequest, owner: User, payload: RequestWrite
) -> AccessRequest:
    if request.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if as_status(request.status) not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Request cannot be edited in this status"
        )
    if submission_blocks_edits(session, request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Edits are blocked while a submission is pending, in flight, unknown, "
                "or the request is forwarding/forwarded"
            ),
        )
    locked = session.execute(
        select(AccessRequest).where(AccessRequest.id == request.id).with_for_update()
    ).scalar_one()
    apply_write(locked, payload)
    locked.revision += 1
    try:
        ensure_transition(locked.status, RequestStatus.PREPARING)
        prepare_proposal(session, locked, owner.id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record_audit(
        session,
        event_type="request_updated",
        actor_id=owner.id,
        request_id=locked.id,
        metadata={"status": as_status(locked.status).value, "revision": locked.revision},
    )
    session.commit()
    return reload_request(session, locked.id)


def resubmit_request(session: Session, request: AccessRequest, owner: User) -> AccessRequest:
    if request.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if as_status(request.status) not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request cannot be resubmitted in this status",
        )
    if submission_blocks_edits(session, request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Resubmit is blocked while a submission is pending, in flight, unknown, "
                "or the request is forwarding/forwarded"
            ),
        )
    locked = session.execute(
        select(AccessRequest).where(AccessRequest.id == request.id).with_for_update()
    ).scalar_one()
    locked.revision += 1
    try:
        ensure_transition(locked.status, RequestStatus.PREPARING)
        prepare_proposal(session, locked, owner.id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    record_audit(
        session,
        event_type="request_updated",
        actor_id=owner.id,
        request_id=locked.id,
        metadata={"status": as_status(locked.status).value, "revision": locked.revision},
    )
    session.commit()
    return reload_request(session, locked.id)


def reload_request(session: Session, request_id: UUID) -> AccessRequest:
    return (
        session.execute(
            select(AccessRequest)
            .options(joinedload(AccessRequest.current_proposal))
            .where(AccessRequest.id == request_id)
        )
        .unique()
        .scalar_one()
    )


def get_request_for_user(session: Session, request_id: UUID, user: User) -> AccessRequest:
    request = (
        session.execute(
            select(AccessRequest)
            .options(joinedload(AccessRequest.current_proposal), joinedload(AccessRequest.owner))
            .where(AccessRequest.id == request_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if user.role == UserRole.REQUESTER and request.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if user.role not in {UserRole.REQUESTER, UserRole.REVIEWER, UserRole.OPERATOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return request


def list_requests(session: Session, user: User) -> list[AccessRequest]:
    query = (
        select(AccessRequest)
        .options(joinedload(AccessRequest.current_proposal))
        .order_by(AccessRequest.created_at.desc())
    )
    if user.role == UserRole.REQUESTER:
        query = query.where(AccessRequest.owner_id == user.id)
    elif user.role == UserRole.REVIEWER:
        query = query.where(
            AccessRequest.status.in_(
                [
                    RequestStatus.READY_FOR_REVIEW,
                    RequestStatus.IN_REVIEW,
                    RequestStatus.APPROVED,
                    RequestStatus.REJECTED,
                    RequestStatus.FORWARDING,
                    RequestStatus.FORWARDED,
                    RequestStatus.FORWARD_FAILED,
                ]
            )
        )
    elif user.role != UserRole.OPERATOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return list(session.scalars(query).unique().all())
