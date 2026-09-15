from datetime import date

from app.models import RequestStatus
from app.rules.engine import evaluate_rules, is_approvable
from app.rules.hashing import payload_hash
from app.rules.policy import load_policy
from app.rules.transitions import InvalidTransitionError, ensure_transition


def _policy():
    return load_policy()


def _base_fields(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "employee_identifier": "EMP-1001",
        "employment_type": "vakituinen",
        "job_role": "sairaanhoitaja",
        "unit": "demo-osasto",
        "target_system": "demo-hr-testi",
        "requested_access_role": "lukuoikeus",
        "start_date": "2026-10-01",
        "end_date": None,
    }
    fields.update(overrides)
    return fields


def test_valid_combination_is_approvable() -> None:
    missing, violations = evaluate_rules(_base_fields(), _policy())
    assert missing == []
    assert violations == []
    assert is_approvable(missing, violations)


def test_required_fields_are_reported() -> None:
    missing, violations = evaluate_rules(
        _base_fields(employee_identifier=None, target_system=None), _policy()
    )
    assert "employee_identifier" in missing
    assert "target_system" in missing
    assert not is_approvable(missing, violations)


def test_unknown_system_requires_clarification() -> None:
    _, violations = evaluate_rules(_base_fields(target_system="tuntematon-jarjestelma"), _policy())
    assert any(item["code"] == "unknown_system" for item in violations)


def test_unknown_role_requires_clarification() -> None:
    _, violations = evaluate_rules(_base_fields(requested_access_role="erikoisoikeus"), _policy())
    assert any(item["code"] == "unknown_access_role" for item in violations)


def test_prohibited_role_cannot_be_approved() -> None:
    _, violations = evaluate_rules(
        _base_fields(requested_access_role="tuotanto-superadmin"), _policy()
    )
    assert any(item["code"] == "prohibited_role" for item in violations)
    assert not is_approvable([], violations)


def test_disallowed_job_access_combination() -> None:
    _, violations = evaluate_rules(
        _base_fields(job_role="laakari", requested_access_role="kirjaaja", end_date="2026-10-15"),
        _policy(),
    )
    assert any(item["code"] == "disallowed_combination" for item in violations)


def test_temporary_access_requires_end_date() -> None:
    missing, violations = evaluate_rules(_base_fields(requested_access_role="kirjaaja"), _policy())
    assert "end_date" in missing
    assert any(item["code"] == "temporary_requires_end_date" for item in violations)


def test_start_date_must_not_exceed_end_date() -> None:
    _, violations = evaluate_rules(
        _base_fields(start_date=date(2026, 11, 1), end_date=date(2026, 10, 1)),
        _policy(),
    )
    assert any(item["code"] == "start_after_end" for item in violations)


def test_payload_hash_is_canonical() -> None:
    first = payload_hash({"b": 2, "a": 1})
    second = payload_hash({"a": 1, "b": 2})
    assert first == second
    assert first != payload_hash({"a": 1, "b": 3})


def test_illegal_transition_is_rejected() -> None:
    try:
        ensure_transition(RequestStatus.SUBMITTED, RequestStatus.APPROVED)
    except InvalidTransitionError:
        return
    raise AssertionError("expected InvalidTransitionError")


def test_review_to_approved_is_allowed() -> None:
    ensure_transition(RequestStatus.READY_FOR_REVIEW, RequestStatus.APPROVED)
    ensure_transition(RequestStatus.IN_REVIEW, RequestStatus.REJECTED)
