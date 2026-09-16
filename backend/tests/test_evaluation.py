from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.evaluation.loader import DATASET_VERSION, filter_cases, load_cases
from app.evaluation.runner import run_evaluation, write_report
from app.models import User
from tests.conftest import REQUESTER_EMAIL, TEST_SETTINGS


def test_evaluation_dataset_has_minimum_cases_and_held_out_split() -> None:
    cases = load_cases()
    assert len(cases) >= 30
    held_out = filter_cases(cases, split="held_out")
    train = filter_cases(cases, split="train")
    assert len(held_out) >= 10
    assert len(train) >= 20
    categories = {case.category for case in cases}
    for required in {
        "complete",
        "missing_fields",
        "prohibited",
        "ambiguous",
        "evidence",
        "prompt_injection",
        "integration",
    }:
        assert required in categories


def test_held_out_evaluation_passes(isolated_db: None) -> None:
    from app.core.db import create_db_engine, create_session_factory

    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            requester = session.scalar(select(User).where(User.email == REQUESTER_EMAIL))
            assert requester is not None
            report = run_evaluation(session, requester, split="held_out")
            failures = [item for item in report.case_results if not item.passed]
            assert not failures, json.dumps(
                [{"id": item.case_id, "failures": item.failures} for item in failures],
                ensure_ascii=False,
                indent=2,
            )
            assert report.cases_passed == report.cases_total
            assert report.provider == "fake"
            assert report.real_model_ran is False
            assert report.dataset_version == DATASET_VERSION
            out_dir = Path(__file__).resolve().parents[2] / "docs" / "results"
            write_report(report, out_dir / "evaluation-held-out-fake.json")
            markdown = _render_markdown(report)
            (out_dir / "evaluation-held-out-fake.md").write_text(markdown, encoding="utf-8")
    finally:
        engine.dispose()


def _render_markdown(report) -> str:  # noqa: ANN001
    lines = [
        "# Evaluation report (fake provider, held-out split)",
        "",
        "**Not clinically validated. Synthetic demo only.**",
        "",
        f"- Dataset: `{report.dataset_version}`",
        f"- Policy: `{report.policy_version}`",
        f"- Prompt: `{report.prompt_version}`",
        f"- Provider: `{report.provider}` (real model run: **{report.real_model_ran}**)",
        f"- Cases: **{report.cases_passed}/{report.cases_total} passed**",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Field extraction accuracy | {report.field_extraction_accuracy:.3f} |",
        f"| Missing-field precision | {report.missing_field_precision:.3f} |",
        f"| Missing-field recall | {report.missing_field_recall:.3f} |",
        f"| Retrieval recall@k | {report.retrieval_recall_at_k:.3f} |",
        f"| Citation validity | {report.citation_validity_rate:.3f} |",
        f"| Routing accuracy | {report.routing_accuracy:.3f} |",
        f"| Approvable accuracy | {report.approvable_accuracy:.3f} |",
        f"| Latency p50 (ms) | {report.latency_ms_p50} |",
        f"| Latency p95 (ms) | {report.latency_ms_p95} |",
        "",
        "## Control checks (pytest suites)",
        "",
        (
            f"- Approval boundary: {report.approval_boundary_checks_passed}/"
            f"{report.approval_boundary_checks_total} scenarios covered"
        ),
        (
            f"- Duplicate submission: {report.duplicate_submission_checks_passed}/"
            f"{report.duplicate_submission_checks_total} scenarios covered"
        ),
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in report.limitations)
    lines.append("")
    return "\n".join(lines)
