from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AccessRequest,
    Approval,
    ApprovalDecision,
    Proposal,
    RequestStatus,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from app.rules.engine import is_approvable
from app.rules.transitions import (
    REVIEWABLE_STATUSES,
    InvalidTransitionError,
    as_status,
    ensure_transition,
)
from app.schemas.requests import ApprovalAction
from app.services.audit import record_audit
from app.services.requests import reload_request


def _lock_request(session: Session, request_id: UUID) -> AccessRequest:
    request = session.execute(
        select(AccessRequest).where(AccessRequest.id == request_id).with_for_update()
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def decide(
    session: Session,
    request_id: UUID,
    reviewer: User,
    action: ApprovalAction,
    decision: ApprovalDecision,
) -> AccessRequest:
    if reviewer.role != UserRole.REVIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only reviewers can decide"
        )
    request = _lock_request(session, request_id)
    if request.owner_id == reviewer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval is not allowed"
        )
    if as_status(request.status) not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Request is not awaiting review"
        )
    if request.current_proposal_id != action.proposal_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stale proposal")
    if request.revision != action.revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stale revision")
    proposal = session.get(Proposal, request.current_proposal_id)
    if proposal is None or proposal.invalidated_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal is not current")
    if (
        proposal.payload_hash != action.payload_hash
        or proposal.policy_version != action.policy_version
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Payload or policy version mismatch"
        )
    if proposal.revision != action.revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stale revision")

    if decision == ApprovalDecision.APPROVE:
        missing = list(proposal.missing_fields)
        violations = list(proposal.rule_violations)
        if not is_approvable(missing, violations):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Policy violations must be resolved before approval",
            )
        target = RequestStatus.APPROVED
    else:
        target = RequestStatus.REJECTED

    try:
        ensure_transition(request.status, target)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    approval = Approval(
        proposal_id=proposal.id,
        request_id=request.id,
        revision=request.revision,
        payload_hash=proposal.payload_hash,
        policy_version=proposal.policy_version,
        reviewer_id=reviewer.id,
        decision=decision,
        comment=action.comment,
    )
    session.add(approval)
    request.status = target
    if decision == ApprovalDecision.APPROVE:
        session.add(
            Submission(
                approved_proposal_id=proposal.id,
                request_id=request.id,
                idempotency_key=f"{request.id}:{proposal.payload_hash}",
                status=SubmissionStatus.PENDING,
                attempt_count=0,
                error_category=None,
            )
        )
    record_audit(
        session,
        event_type="review_approved" if decision == ApprovalDecision.APPROVE else "review_rejected",
        actor_id=reviewer.id,
        request_id=request.id,
        metadata={
            "decision": decision.value,
            "revision": request.revision,
            "proposal_id": str(proposal.id),
            "policy_version": proposal.policy_version,
            "status": target.value,
        },
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Concurrent approval"
        ) from exc
    return reload_request(session, request.id)


def start_review(session: Session, request_id: UUID, reviewer: User) -> AccessRequest:
    if reviewer.role != UserRole.REVIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only reviewers can decide"
        )
    request = _lock_request(session, request_id)
    if request.owner_id == reviewer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval is not allowed"
        )
    if as_status(request.status) == RequestStatus.IN_REVIEW:
        return request
    if as_status(request.status) not in REVIEWABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Request is not awaiting review"
        )
    try:
        ensure_transition(request.status, RequestStatus.IN_REVIEW)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    request.status = RequestStatus.IN_REVIEW
    record_audit(
        session,
        event_type="review_started",
        actor_id=reviewer.id,
        request_id=request.id,
        metadata={"status": RequestStatus.IN_REVIEW.value, "revision": request.revision},
    )
    session.commit()
    return reload_request(session, request.id)
