from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import AccessRequest, Proposal, RequestStatus
from app.rules.engine import evaluate_rules, is_approvable
from app.rules.hashing import payload_hash
from app.rules.policy import PolicyConfig, current_policy
from app.rules.transitions import ensure_transition
from app.services.audit import record_audit


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def request_fields(request: AccessRequest) -> dict[str, Any]:
    return {
        "employee_identifier": request.employee_identifier,
        "employment_type": request.employment_type,
        "job_role": request.job_role,
        "unit": request.unit,
        "target_system": request.target_system,
        "requested_access_role": request.requested_access_role,
        "start_date": _iso(request.start_date),
        "end_date": _iso(request.end_date),
    }


def build_excerpts(original_text: str, fields: dict[str, Any]) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for key, value in fields.items():
        if isinstance(value, str) and value and value in original_text:
            excerpts[key] = value
    return excerpts


def prepare_proposal(
    session: Session,
    request: AccessRequest,
    actor_id: UUID,
    policy: PolicyConfig | None = None,
) -> Proposal:
    policy = policy or current_policy()
    ensure_transition(request.status, RequestStatus.PREPARING)
    request.status = RequestStatus.PREPARING

    if request.current_proposal_id is not None:
        previous = session.get(Proposal, request.current_proposal_id)
        if previous is not None and previous.invalidated_at is None:
            previous.invalidated_at = datetime.now(UTC)
            record_audit(
                session,
                event_type="proposal_invalidated",
                actor_id=actor_id,
                request_id=request.id,
                metadata={"revision": previous.revision, "proposal_id": str(previous.id)},
            )

    fields = request_fields(request)
    missing, violations = evaluate_rules(fields, policy)
    excerpts = build_excerpts(request.original_text, fields)
    downstream = {
        "employee_identifier": request.employee_identifier,
        "target_system": request.target_system,
        "requested_access_role": request.requested_access_role,
        "start_date": _iso(request.start_date),
        "end_date": _iso(request.end_date),
        "revision": request.revision,
        "policy_version": policy.version,
    }
    digest = payload_hash(downstream)
    explanation = _explain(missing, violations, policy.version)
    proposal = Proposal(
        id=uuid4(),
        request_id=request.id,
        revision=request.revision,
        extracted_fields=fields,
        excerpts=excerpts,
        missing_fields=missing,
        rule_violations=violations,
        explanation_text=explanation,
        source_references=[{"policy_version": policy.version, "source": policy.source}],
        downstream_payload=downstream,
        policy_version=policy.version,
        payload_hash=digest,
    )
    session.add(proposal)
    session.flush()
    request.current_proposal_id = proposal.id
    next_status = (
        RequestStatus.READY_FOR_REVIEW
        if is_approvable(missing, violations)
        else RequestStatus.NEEDS_CLARIFICATION
    )
    ensure_transition(request.status, next_status)
    request.status = next_status
    record_audit(
        session,
        event_type="proposal_prepared",
        actor_id=actor_id,
        request_id=request.id,
        metadata={
            "revision": request.revision,
            "proposal_id": str(proposal.id),
            "status": next_status.value,
            "missing_fields": missing,
            "violation_codes": [item["code"] for item in violations],
            "policy_version": policy.version,
        },
    )
    return proposal


def _explain(missing: list[str], violations: list[dict[str, str]], policy_version: str) -> str:
    if not missing and not violations:
        return (
            f"Deterministic checks against {policy_version} found no blocking issues. "
            "Human review is still required."
        )
    parts = [f"Deterministic checks against {policy_version}:"]
    if missing:
        parts.append("Missing fields: " + ", ".join(missing) + ".")
    for item in violations:
        parts.append(item["message"])
    return " ".join(parts)
