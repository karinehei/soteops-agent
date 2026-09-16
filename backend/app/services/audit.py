from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import correlation_id_ctx
from app.models import AuditEvent

ALLOWED_METADATA_KEYS = frozenset(
    {
        "status",
        "revision",
        "proposal_id",
        "decision",
        "policy_version",
        "missing_fields",
        "violation_codes",
        "node",
        "provider",
        "run_status",
        "source_ids",
        "attempt_count",
        "error_category",
        "submission_status",
        "downstream_reference",
    }
)


def record_audit(
    session: Session,
    *,
    event_type: str,
    actor_id: UUID | None,
    request_id: UUID | None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    cleaned = {
        key: value for key, value in (metadata or {}).items() if key in ALLOWED_METADATA_KEYS
    }
    event = AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        request_id=request_id,
        correlation_id=correlation_id_ctx.get(),
        metadata_json=cleaned,
    )
    session.add(event)
    session.flush()
    return event
