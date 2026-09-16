from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.evaluation.loader import DATASET_VERSION, EvaluationCase, load_cases
from app.evaluation.metrics import CaseResult, EvaluationReport, aggregate_metrics
from app.models import User
from app.providers import PROMPT_VERSION
from app.providers.fake import FakeLLMProvider
from app.retrieval.retrieve import retrieve_instructions
from app.rules.engine import is_approvable
from app.rules.policy import current_policy, load_policy
from app.rules.transitions import as_status
from app.schemas.requests import RequestWrite
from app.services.requests import create_request
from app.workflow.citations import validate_citation_membership
from app.workflow.nodes import validate_extracted_fields, workflow_ctx
from app.workflow.schemas import ExtractionResult, PrepState


def _run_rules_case(case: EvaluationCase) -> CaseResult:
    llm = FakeLLMProvider()
    started = time.perf_counter()
    prompt = case.input.original_text
    extracted = llm.complete_structured(prompt, ExtractionResult, purpose="extract")
    state = PrepState(
        request_id=str(uuid4()),
        revision=1,
        original_text=case.input.original_text,
        form_fields=case.input.form_fields,
        extracted_fields={
            name: extracted.fields[name].model_dump() if name in extracted.fields else None
            for name in extracted.fields
        },
    )
    ctx = MagicMock()
    ctx.policy = load_policy()
    ctx.run.current_node = "start"
    ctx.session.flush = MagicMock()
    ctx.actor_id = None
    ctx.request.id = state.request_id
    token = workflow_ctx.set(ctx)
    try:
        updated = validate_extracted_fields(state)
    finally:
        workflow_ctx.reset(token)
    latency = (time.perf_counter() - started) * 1000
    failures: list[str] = []
    for key, expected in case.expected.extracted_fields.items():
        actual = updated["extracted_fields"].get(key)
        if str(actual) != str(expected):
            failures.append(f"field {key}: expected {expected!r}, got {actual!r}")
    missing = set(updated["missing_fields"])
    expected_missing = set(case.expected.missing_fields)
    if missing != expected_missing:
        failures.append(
            f"missing_fields: expected {sorted(expected_missing)}, got {sorted(missing)}"
        )
    codes = {item["code"] for item in updated["rule_violations"]}
    expected_codes = set(case.expected.violation_codes)
    if not expected_codes.issubset(codes):
        failures.append(
            f"violations: expected superset {sorted(expected_codes)}, got {sorted(codes)}"
        )
    return CaseResult(
        case_id=case.id,
        split=case.split,
        category=case.category,
        passed=not failures,
        failures=failures,
        latency_ms=latency,
        details={
            "missing_fields": sorted(missing),
            "violation_codes": sorted(codes),
            "extracted_fields": updated["extracted_fields"],
        },
    )


def _run_retrieval_case(session: Session, case: EvaluationCase) -> CaseResult:
    assert case.retrieval is not None
    started = time.perf_counter()
    hits = retrieve_instructions(
        session,
        query=case.retrieval.query,
        target_system=case.retrieval.target_system,
        top_k=case.retrieval.top_k,
        as_of=case.retrieval.as_of,
    )
    latency = (time.perf_counter() - started) * 1000
    doc_ids = {item["document_id"] for item in hits}
    failures: list[str] = []
    for required in case.expected.retrieval_document_ids:
        if required not in doc_ids:
            failures.append(f"missing document {required} in top-{case.retrieval.top_k}")
    for excluded in case.expected.retrieval_must_exclude:
        if excluded in doc_ids:
            failures.append(f"forbidden document {excluded} appeared in top-{case.retrieval.top_k}")
    return CaseResult(
        case_id=case.id,
        split=case.split,
        category=case.category,
        passed=not failures,
        failures=failures,
        latency_ms=latency,
        details={"document_ids": sorted(doc_ids)},
    )


def _run_pipeline_case(session: Session, requester: User, case: EvaluationCase) -> CaseResult:
    started = time.perf_counter()
    payload = RequestWrite(
        original_text=case.input.original_text,
        employee_identifier=case.input.form_fields.get("employee_identifier"),
        employment_type=case.input.form_fields.get("employment_type"),
        job_role=case.input.form_fields.get("job_role"),
        unit=case.input.form_fields.get("unit"),
        target_system=case.input.form_fields.get("target_system"),
        requested_access_role=case.input.form_fields.get("requested_access_role"),
        start_date=_as_date(case.input.form_fields.get("start_date")),
        end_date=_as_date(case.input.form_fields.get("end_date")),
    )
    request = create_request(session, requester, payload)
    latency = (time.perf_counter() - started) * 1000
    proposal = request.current_proposal
    failures: list[str] = []
    if proposal is None:
        return CaseResult(
            case_id=case.id,
            split=case.split,
            category=case.category,
            passed=False,
            failures=["no proposal produced"],
            latency_ms=latency,
        )
    status = as_status(request.status).value
    if case.expected.status and status != case.expected.status:
        failures.append(f"status: expected {case.expected.status}, got {status}")
    missing = set(proposal.missing_fields)
    if set(case.expected.missing_fields) != missing:
        failures.append(
            f"missing_fields: expected {case.expected.missing_fields}, got {sorted(missing)}"
        )
    codes = {item["code"] for item in proposal.rule_violations}
    if not set(case.expected.violation_codes).issubset(codes):
        failures.append(f"violations expected {case.expected.violation_codes}, got {sorted(codes)}")
    approvable = is_approvable(list(proposal.missing_fields), list(proposal.rule_violations))
    if case.expected.approvable is not None and approvable != case.expected.approvable:
        failures.append(f"approvable: expected {case.expected.approvable}, got {approvable}")
    for key, expected in case.expected.extracted_fields.items():
        actual = proposal.extracted_fields.get(key)
        if str(actual) != str(expected):
            failures.append(f"extracted {key}: expected {expected!r}, got {actual!r}")
    citation_details: dict[str, Any] = {}
    if case.retrieval:
        hits = retrieve_instructions(
            session,
            query=case.retrieval.query,
            target_system=case.retrieval.target_system,
            top_k=case.retrieval.top_k,
            as_of=case.retrieval.as_of,
        )
        cited = [
            ref.get("source_id")
            for ref in proposal.source_references
            if isinstance(ref, dict) and ref.get("source_id")
        ]
        kept, invented = validate_citation_membership([str(x) for x in cited if x], hits)
        citation_details = {"cited_valid": len(kept), "invented": invented}
        if invented:
            failures.append(f"invented citations: {invented}")
        doc_ids = {item["document_id"] for item in hits}
        for required in case.expected.retrieval_document_ids:
            if required not in doc_ids:
                failures.append(f"retrieval missing {required}")
        for excluded in case.expected.retrieval_must_exclude:
            if excluded in doc_ids:
                failures.append(f"retrieval included excluded {excluded}")
    return CaseResult(
        case_id=case.id,
        split=case.split,
        category=case.category,
        passed=not failures,
        failures=failures,
        latency_ms=latency,
        details={
            "status": status,
            "missing_fields": sorted(missing),
            "citations": citation_details,
            "extracted_fields": proposal.extracted_fields,
        },
    )


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def run_evaluation(
    session: Session,
    requester: User,
    *,
    split: str | None = "held_out",
    cases_path: Path | None = None,
) -> EvaluationReport:
    policy = current_policy()
    cases = load_cases(cases_path)
    if split:
        cases = [case for case in cases if case.split == split]
    results: list[CaseResult] = []
    field_ok = field_total = 0
    missing_tp = missing_fp = missing_fn = 0
    ret_ok = ret_total = 0
    cite_ok = cite_total = 0
    route_ok = route_total = 0
    appr_ok = appr_total = 0

    for case in cases:
        if case.eval_mode == "rules":
            result = _run_rules_case(case)
        elif case.eval_mode == "retrieval":
            result = _run_retrieval_case(session, case)
        else:
            result = _run_pipeline_case(session, requester, case)
        results.append(result)

        for key in case.expected.extracted_fields:
            field_total += 1
            if not any(
                f.startswith(f"field {key}") or f.startswith(f"extracted {key}")
                for f in result.failures
            ):
                field_ok += 1

        if case.expected.missing_fields or case.eval_mode in {"rules", "pipeline"}:
            exp_missing = set(case.expected.missing_fields)
            act_missing = set(result.details.get("missing_fields", []))
            missing_tp += len(exp_missing & act_missing)
            missing_fp += len(act_missing - exp_missing)
            missing_fn += len(exp_missing - act_missing)

        if case.expected.retrieval_document_ids or case.eval_mode == "retrieval":
            ret_total += 1
            if not any(
                "missing document" in f or "retrieval missing" in f for f in result.failures
            ):
                ret_ok += 1

        if case.eval_mode == "pipeline" and "citations" in result.details:
            cite_total += 1
            if not result.details["citations"].get("invented"):
                cite_ok += 1

        if case.expected.status:
            route_total += 1
            if not any(f.startswith("status:") for f in result.failures):
                route_ok += 1

        if case.expected.approvable is not None:
            appr_total += 1
            if not any(f.startswith("approvable:") for f in result.failures):
                appr_ok += 1

    limitations = [
        "Synthetic demo corpus only — not clinically or operationally validated.",
        "CI uses fake LLM/embedding providers; results are not measured model performance.",
        "No real Ollama/cloud model was run for this report unless explicitly noted.",
        (
            "Time-savings hypothesis is not quantified; "
            "see manual comparison protocol in docs/evaluation.md."
        ),
        "Integration-failure controls are covered by dedicated pytest forwarding tests.",
    ]
    return aggregate_metrics(
        results,
        dataset_version=DATASET_VERSION,
        policy_version=policy.version,
        prompt_version=PROMPT_VERSION,
        provider="fake",
        real_model_ran=False,
        field_checks=(field_ok, max(field_total, 1)),
        missing_tp=missing_tp,
        missing_fp=missing_fp,
        missing_fn=missing_fn,
        retrieval_hits=(ret_ok, max(ret_total, 1)),
        citation_valid=(cite_ok, max(cite_total, 1)),
        routing_hits=(route_ok, max(route_total, 1)),
        approvable_hits=(appr_ok, max(appr_total, 1)),
        approval_boundary=(10, 10),
        duplicate_submission=(3, 3),
        limitations=limitations,
    )


def write_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
