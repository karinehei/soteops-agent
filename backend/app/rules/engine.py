from __future__ import annotations

from datetime import date
from typing import Any

from app.rules.policy import PolicyConfig

REQUIRED_FIELD_LABELS = {
    "employee_identifier": "synthetic employee identifier",
    "target_system": "target system",
    "requested_access_role": "requested access role",
    "start_date": "start date",
    "end_date": "end date",
    "job_role": "job role",
    "employment_type": "employment type",
    "unit": "unit",
}


def _as_date(value: date | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def evaluate_rules(
    fields: dict[str, Any], policy: PolicyConfig
) -> tuple[list[str], list[dict[str, str]]]:
    missing: list[str] = []
    violations: list[dict[str, str]] = []

    for field_name in policy.required_fields:
        if fields.get(field_name) in (None, ""):
            missing.append(field_name)

    employment_type = fields.get("employment_type")
    if employment_type and employment_type not in policy.allowed_employment_types:
        violations.append(
            {
                "code": "unknown_employment_type",
                "message": "Unknown employment type requires manual clarification.",
            }
        )

    job_role = fields.get("job_role")
    if job_role and job_role not in policy.allowed_job_roles:
        violations.append(
            {
                "code": "unknown_job_role",
                "message": "Unknown job role requires manual clarification.",
            }
        )

    target_system = fields.get("target_system")
    if target_system and target_system not in policy.allowed_systems:
        violations.append(
            {
                "code": "unknown_system",
                "message": "Unknown target system requires manual clarification.",
            }
        )

    access_role = fields.get("requested_access_role")
    if access_role and access_role in policy.prohibited_access_roles:
        violations.append(
            {
                "code": "prohibited_role",
                "message": "This access role cannot be approved in the normal workflow.",
            }
        )
    elif access_role and access_role not in policy.allowed_access_roles:
        violations.append(
            {
                "code": "unknown_access_role",
                "message": "Unknown access role requires manual clarification.",
            }
        )

    if job_role and access_role and job_role in policy.allowed_job_roles:
        if access_role in policy.allowed_access_roles:
            allowed = any(
                item.job_role == job_role and item.access_role == access_role
                for item in policy.allowed_combinations
            )
            if not allowed:
                violations.append(
                    {
                        "code": "disallowed_combination",
                        "message": "Job role and access role combination is not permitted.",
                    }
                )

    start_date = _as_date(fields.get("start_date"))
    end_date = _as_date(fields.get("end_date"))
    if start_date and end_date and start_date > end_date:
        violations.append(
            {
                "code": "start_after_end",
                "message": "Start date must not exceed end date.",
            }
        )

    if access_role in policy.temporary_access_roles and end_date is None:
        missing.append("end_date")
        violations.append(
            {
                "code": "temporary_requires_end_date",
                "message": "Temporary access requires an end date.",
            }
        )

    unique_missing = list(dict.fromkeys(missing))
    return unique_missing, violations


def is_approvable(missing_fields: list[str], violations: list[dict[str, str]]) -> bool:
    return not missing_fields and not violations
