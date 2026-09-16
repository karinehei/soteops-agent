from app.models import RequestStatus


def as_status(value: RequestStatus | str) -> RequestStatus:
    return value if isinstance(value, RequestStatus) else RequestStatus(value)


ALLOWED_TRANSITIONS: frozenset[tuple[RequestStatus, RequestStatus]] = frozenset(
    {
        (RequestStatus.SUBMITTED, RequestStatus.PREPARING),
        (RequestStatus.PREPARING, RequestStatus.NEEDS_CLARIFICATION),
        (RequestStatus.PREPARING, RequestStatus.READY_FOR_REVIEW),
        (RequestStatus.NEEDS_CLARIFICATION, RequestStatus.PREPARING),
        (RequestStatus.READY_FOR_REVIEW, RequestStatus.IN_REVIEW),
        (RequestStatus.READY_FOR_REVIEW, RequestStatus.APPROVED),
        (RequestStatus.READY_FOR_REVIEW, RequestStatus.REJECTED),
        (RequestStatus.IN_REVIEW, RequestStatus.APPROVED),
        (RequestStatus.IN_REVIEW, RequestStatus.REJECTED),
        (RequestStatus.IN_REVIEW, RequestStatus.NEEDS_CLARIFICATION),
        (RequestStatus.IN_REVIEW, RequestStatus.PREPARING),
        (RequestStatus.READY_FOR_REVIEW, RequestStatus.PREPARING),
        (RequestStatus.APPROVED, RequestStatus.PREPARING),
        (RequestStatus.APPROVED, RequestStatus.FORWARDING),
        (RequestStatus.REJECTED, RequestStatus.PREPARING),
        (RequestStatus.FORWARDING, RequestStatus.FORWARDED),
        (RequestStatus.FORWARDING, RequestStatus.FORWARD_FAILED),
        (RequestStatus.FORWARD_FAILED, RequestStatus.FORWARDING),
        (RequestStatus.FORWARD_FAILED, RequestStatus.PREPARING),
        (RequestStatus.FORWARDING, RequestStatus.PREPARING),
    }
)

EDITABLE_STATUSES = frozenset(
    {
        RequestStatus.NEEDS_CLARIFICATION,
        RequestStatus.READY_FOR_REVIEW,
        RequestStatus.IN_REVIEW,
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
        RequestStatus.SUBMITTED,
        RequestStatus.PREPARING,
        RequestStatus.FORWARD_FAILED,
    }
)

SUBMISSION_BLOCKED_STATUSES = frozenset(
    {
        RequestStatus.FORWARDING,
        RequestStatus.FORWARDED,
    }
)

REVIEWABLE_STATUSES = frozenset({RequestStatus.READY_FOR_REVIEW, RequestStatus.IN_REVIEW})


class InvalidTransitionError(ValueError):
    pass


def ensure_transition(current: RequestStatus | str, target: RequestStatus) -> None:
    current_status = as_status(current)
    if current_status == target:
        return
    if (current_status, target) not in ALLOWED_TRANSITIONS:
        raise InvalidTransitionError(f"Cannot transition from {current_status} to {target}")
