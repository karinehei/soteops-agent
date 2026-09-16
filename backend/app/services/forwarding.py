from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, load_settings
from app.integrations.downstream import (
    DownstreamClient,
    DownstreamOutcome,
    DownstreamResult,
    HttpDownstreamClient,
    outbound_payload,
)
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
from app.rules.policy import current_policy
from app.rules.transitions import (
    SUBMISSION_BLOCKED_STATUSES,
    InvalidTransitionError,
    as_status,
    ensure_transition,
)
from app.services.audit import record_audit

logger = logging.getLogger(__name__)

BLOCKING_SUBMISSION_STATUSES = frozenset(
    {
        SubmissionStatus.PENDING,
        SubmissionStatus.IN_FLIGHT,
        SubmissionStatus.UNKNOWN,
        SubmissionStatus.PENDING.value,
        SubmissionStatus.IN_FLIGHT.value,
        SubmissionStatus.UNKNOWN.value,
    }
)
TERMINAL_SUBMISSION_STATUSES = frozenset(
    {
        SubmissionStatus.ACCEPTED,
        SubmissionStatus.EXHAUSTED,
        SubmissionStatus.CONFLICT,
        SubmissionStatus.ACCEPTED.value,
        SubmissionStatus.EXHAUSTED.value,
        SubmissionStatus.CONFLICT.value,
    }
)


def submission_blocks_edits(session: Session, request: AccessRequest) -> bool:
    if as_status(request.status) in SUBMISSION_BLOCKED_STATUSES:
        return True
    submission = current_submission(session, request.id)
    if submission is None:
        return False
    return submission.status in BLOCKING_SUBMISSION_STATUSES


def current_submission(session: Session, request_id: UUID) -> Submission | None:
    return session.scalar(
        select(Submission)
        .where(Submission.request_id == request_id)
        .order_by(Submission.created_at.desc())
    )


def _lock_request(session: Session, request_id: UUID) -> AccessRequest:
    request = session.execute(
        select(AccessRequest).where(AccessRequest.id == request_id).with_for_update()
    ).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return request


def recover_stale_in_flight(session: Session, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=max(settings.forward_timeout_seconds * 2, 1))
    rows = session.scalars(
        select(Submission).where(
            Submission.status.in_([SubmissionStatus.IN_FLIGHT, "in_flight"]),
            Submission.claimed_at.is_not(None),
            Submission.claimed_at < cutoff,
        )
    ).all()
    for row in rows:
        row.status = SubmissionStatus.UNKNOWN
        row.error_category = "stale_in_flight"
        record_audit(
            session,
            event_type="submission_unknown",
            actor_id=None,
            request_id=row.request_id,
            metadata={
                "submission_status": SubmissionStatus.UNKNOWN.value,
                "error_category": "stale_in_flight",
                "attempt_count": row.attempt_count,
            },
        )
    session.flush()
    return len(rows)


def _bound_approval(session: Session, submission: Submission, proposal: Proposal) -> Approval:
    approval = session.get(Approval, submission.approval_id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bound approval is missing"
        )
    if approval.decision not in {ApprovalDecision.APPROVE, ApprovalDecision.APPROVE.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bound approval is not an approve"
        )
    if approval.proposal_id != proposal.id or approval.payload_hash != proposal.payload_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Approval does not match proposal"
        )
    if approval.revision != proposal.revision or approval.policy_version != proposal.policy_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Approval revision or policy mismatch"
        )
    return approval


def _verify_before_send(
    session: Session, request: AccessRequest, submission: Submission, settings: Settings
) -> Proposal:
    if request.current_proposal_id != submission.approved_proposal_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Stale proposal cannot be submitted"
        )
    proposal = session.get(Proposal, submission.approved_proposal_id)
    if proposal is None or proposal.invalidated_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal is not current")
    if proposal.payload_hash != submission.payload_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Submission hash does not match proposal"
        )
    if proposal.revision != submission.revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Submission revision mismatch"
        )
    policy = current_policy(settings.policy_file)
    if (
        proposal.policy_version != submission.policy_version
        or proposal.policy_version != policy.version
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Applicable policy does not match"
        )
    _bound_approval(session, submission, proposal)
    return proposal


def _apply_outcome(
    session: Session,
    request: AccessRequest,
    submission: Submission,
    actor_id: UUID | None,
    outcome: DownstreamOutcome,
    *,
    record_id: str | None,
    error_category: str | None,
    max_attempts: int,
) -> None:
    if outcome == DownstreamOutcome.ACCEPTED:
        submission.status = SubmissionStatus.ACCEPTED
        submission.downstream_reference = record_id
        submission.error_category = None
        ensure_transition(request.status, RequestStatus.FORWARDED)
        request.status = RequestStatus.FORWARDED
        record_audit(
            session,
            event_type="submission_accepted",
            actor_id=actor_id,
            request_id=request.id,
            metadata={
                "status": RequestStatus.FORWARDED.value,
                "submission_status": SubmissionStatus.ACCEPTED.value,
                "attempt_count": submission.attempt_count,
                "downstream_reference": record_id,
                "revision": request.revision,
            },
        )
        return
    if outcome == DownstreamOutcome.CONFLICT:
        submission.status = SubmissionStatus.CONFLICT
        submission.error_category = error_category or "idempotency_conflict"
        ensure_transition(request.status, RequestStatus.FORWARD_FAILED)
        request.status = RequestStatus.FORWARD_FAILED
        record_audit(
            session,
            event_type="submission_failed",
            actor_id=actor_id,
            request_id=request.id,
            metadata={
                "status": RequestStatus.FORWARD_FAILED.value,
                "submission_status": SubmissionStatus.CONFLICT.value,
                "error_category": submission.error_category,
                "attempt_count": submission.attempt_count,
            },
        )
        return
    if outcome == DownstreamOutcome.UNKNOWN:
        submission.status = SubmissionStatus.UNKNOWN
        submission.error_category = error_category or "unknown"
        if as_status(request.status) != RequestStatus.FORWARDING:
            ensure_transition(request.status, RequestStatus.FORWARDING)
            request.status = RequestStatus.FORWARDING
        record_audit(
            session,
            event_type="submission_unknown",
            actor_id=actor_id,
            request_id=request.id,
            metadata={
                "status": RequestStatus.FORWARDING.value,
                "submission_status": SubmissionStatus.UNKNOWN.value,
                "error_category": submission.error_category,
                "attempt_count": submission.attempt_count,
            },
        )
        return
    if submission.attempt_count >= max_attempts:
        submission.status = SubmissionStatus.EXHAUSTED
        submission.error_category = error_category or "retry_limit"
        ensure_transition(request.status, RequestStatus.FORWARD_FAILED)
        request.status = RequestStatus.FORWARD_FAILED
        record_audit(
            session,
            event_type="submission_exhausted",
            actor_id=actor_id,
            request_id=request.id,
            metadata={
                "status": RequestStatus.FORWARD_FAILED.value,
                "submission_status": SubmissionStatus.EXHAUSTED.value,
                "error_category": submission.error_category,
                "attempt_count": submission.attempt_count,
            },
        )
        return
    submission.status = SubmissionStatus.FAILED
    submission.error_category = error_category or "failed"
    ensure_transition(request.status, RequestStatus.FORWARD_FAILED)
    request.status = RequestStatus.FORWARD_FAILED
    record_audit(
        session,
        event_type="submission_failed",
        actor_id=actor_id,
        request_id=request.id,
        metadata={
            "status": RequestStatus.FORWARD_FAILED.value,
            "submission_status": SubmissionStatus.FAILED.value,
            "error_category": submission.error_category,
            "attempt_count": submission.attempt_count,
        },
    )


def _reconcile_unknown(
    transport: DownstreamClient,
    idempotency_key: str,
    expected_hash: str,
    posted: DownstreamResult,
) -> DownstreamResult:
    lookup = transport.get_request(idempotency_key)
    if lookup.outcome == DownstreamOutcome.ACCEPTED:
        if lookup.payload_hash and lookup.payload_hash != expected_hash:
            return DownstreamResult(
                outcome=DownstreamOutcome.CONFLICT,
                record_id=lookup.record_id,
                payload_hash=lookup.payload_hash,
                error_category="idempotency_conflict",
            )
        return lookup
    if lookup.outcome == DownstreamOutcome.MISSING:
        return DownstreamResult(
            outcome=DownstreamOutcome.FAILED,
            error_category=posted.error_category or "not_found_after_unknown",
            status_code=lookup.status_code,
        )
    if lookup.outcome == DownstreamOutcome.CONFLICT:
        return lookup
    return posted


def dispatch_submission(
    session: Session,
    submission_id: UUID,
    actor_id: UUID | None,
    settings: Settings | None = None,
    client: DownstreamClient | None = None,
    *,
    fault: str | None = None,
) -> Submission:
    settings = settings or load_settings()
    recover_stale_in_flight(session, settings)
    peek = session.get(Submission, submission_id)
    if peek is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    request = _lock_request(session, peek.request_id)
    submission = session.execute(
        select(Submission).where(Submission.id == submission_id).with_for_update()
    ).scalar_one()
    if submission.status in TERMINAL_SUBMISSION_STATUSES:
        return submission
    retryable_unknown = submission.status in {
        SubmissionStatus.UNKNOWN,
        SubmissionStatus.UNKNOWN.value,
    }
    if submission.attempt_count >= settings.forward_max_attempts and not retryable_unknown:
        _apply_outcome(
            session,
            request,
            submission,
            actor_id,
            DownstreamOutcome.FAILED,
            record_id=None,
            error_category="retry_limit",
            max_attempts=settings.forward_max_attempts,
        )
        session.commit()
        return submission
    try:
        proposal = _verify_before_send(session, request, submission, settings)
    except HTTPException:
        submission.status = SubmissionStatus.FAILED
        submission.error_category = "verification_failed"
        if as_status(request.status) in {RequestStatus.APPROVED, RequestStatus.FORWARDING}:
            try:
                ensure_transition(request.status, RequestStatus.FORWARD_FAILED)
            except InvalidTransitionError:
                pass
            else:
                request.status = RequestStatus.FORWARD_FAILED
        session.commit()
        raise
    if as_status(request.status) in {RequestStatus.APPROVED, RequestStatus.FORWARD_FAILED}:
        ensure_transition(request.status, RequestStatus.FORWARDING)
        request.status = RequestStatus.FORWARDING
    transport = client or HttpDownstreamClient(settings)
    if retryable_unknown:
        looked = transport.get_request(submission.idempotency_key)
        if looked.outcome == DownstreamOutcome.ACCEPTED:
            accepted_or_conflict = (
                DownstreamOutcome.CONFLICT
                if looked.payload_hash and looked.payload_hash != proposal.payload_hash
                else DownstreamOutcome.ACCEPTED
            )
            _apply_outcome(
                session,
                request,
                submission,
                actor_id,
                accepted_or_conflict,
                record_id=looked.record_id,
                error_category=(
                    "idempotency_conflict"
                    if accepted_or_conflict == DownstreamOutcome.CONFLICT
                    else None
                ),
                max_attempts=settings.forward_max_attempts,
            )
            session.commit()
            return submission
        if looked.outcome == DownstreamOutcome.CONFLICT:
            _apply_outcome(
                session,
                request,
                submission,
                actor_id,
                DownstreamOutcome.CONFLICT,
                record_id=looked.record_id,
                error_category=looked.error_category,
                max_attempts=settings.forward_max_attempts,
            )
            session.commit()
            return submission
        if submission.attempt_count >= settings.forward_max_attempts:
            _apply_outcome(
                session,
                request,
                submission,
                actor_id,
                DownstreamOutcome.FAILED,
                record_id=None,
                error_category="retry_limit",
                max_attempts=settings.forward_max_attempts,
            )
            session.commit()
            return submission
    now = datetime.now(UTC)
    submission.status = SubmissionStatus.IN_FLIGHT
    submission.attempt_count += 1
    submission.claimed_at = now
    submission.last_attempt_at = now
    record_audit(
        session,
        event_type="submission_attempt",
        actor_id=actor_id,
        request_id=request.id,
        metadata={
            "status": RequestStatus.FORWARDING.value,
            "submission_status": SubmissionStatus.IN_FLIGHT.value,
            "attempt_count": submission.attempt_count,
            "revision": request.revision,
        },
    )
    session.commit()

    logger.info(
        "downstream attempt request_id=%s attempts=%s",
        request.id,
        submission.attempt_count,
    )
    body = outbound_payload(proposal.downstream_payload, proposal.payload_hash)
    result = transport.post_request(submission.idempotency_key, body, fault=fault)
    if result.outcome == DownstreamOutcome.UNKNOWN:
        result = _reconcile_unknown(
            transport, submission.idempotency_key, proposal.payload_hash, result
        )

    request = _lock_request(session, submission.request_id)
    submission = session.execute(
        select(Submission).where(Submission.id == submission.id).with_for_update()
    ).scalar_one()
    _apply_outcome(
        session,
        request,
        submission,
        actor_id,
        result.outcome,
        record_id=result.record_id,
        error_category=result.error_category,
        max_attempts=settings.forward_max_attempts,
    )
    session.commit()
    return submission


def dispatch_request(
    session: Session,
    request_id: UUID,
    actor: User,
    settings: Settings | None = None,
    client: DownstreamClient | None = None,
    *,
    fault: str | None = None,
) -> AccessRequest:
    if actor.role not in {UserRole.REVIEWER, UserRole.OPERATOR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only reviewers or operators can forward",
        )
    settings = settings or load_settings()
    request = _lock_request(session, request_id)
    submission = current_submission(session, request.id)
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No scheduled submission for this request"
        )
    if as_status(request.status) == RequestStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Rejected proposals cannot be submitted"
        )
    if submission.status in {SubmissionStatus.EXHAUSTED, SubmissionStatus.EXHAUSTED.value}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Retries stopped at FORWARD_MAX_ATTEMPTS={settings.forward_max_attempts}",
        )
    session.commit()
    dispatch_submission(
        session, submission.id, actor.id, settings=settings, client=client, fault=fault
    )
    from app.services.requests import reload_request

    return reload_request(session, request_id)
