from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    case_id: str
    split: str
    category: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    latency_ms: float | None = None


@dataclass
class EvaluationReport:
    dataset_version: str
    policy_version: str
    prompt_version: str
    provider: str
    real_model_ran: bool
    cases_total: int
    cases_passed: int
    field_extraction_accuracy: float
    missing_field_precision: float
    missing_field_recall: float
    retrieval_recall_at_k: float
    citation_validity_rate: float
    routing_accuracy: float
    approvable_accuracy: float
    latency_ms_p50: float | None
    latency_ms_p95: float | None
    approval_boundary_checks_passed: int
    approval_boundary_checks_total: int
    duplicate_submission_checks_passed: int
    duplicate_submission_checks_total: int
    case_results: list[CaseResult]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "policy_version": self.policy_version,
            "prompt_version": self.prompt_version,
            "provider": self.provider,
            "real_model_ran": self.real_model_ran,
            "cases_total": self.cases_total,
            "cases_passed": self.cases_passed,
            "metrics": {
                "field_extraction_accuracy": self.field_extraction_accuracy,
                "missing_field_precision": self.missing_field_precision,
                "missing_field_recall": self.missing_field_recall,
                "retrieval_recall_at_k": self.retrieval_recall_at_k,
                "citation_validity_rate": self.citation_validity_rate,
                "routing_accuracy": self.routing_accuracy,
                "approvable_accuracy": self.approvable_accuracy,
                "latency_ms_p50": self.latency_ms_p50,
                "latency_ms_p95": self.latency_ms_p95,
            },
            "control_checks": {
                "approval_boundary_passed": self.approval_boundary_checks_passed,
                "approval_boundary_total": self.approval_boundary_checks_total,
                "duplicate_submission_passed": self.duplicate_submission_checks_passed,
                "duplicate_submission_total": self.duplicate_submission_checks_total,
            },
            "limitations": self.limitations,
            "cases": [
                {
                    "id": item.case_id,
                    "split": item.split,
                    "category": item.category,
                    "passed": item.passed,
                    "failures": item.failures,
                    "latency_ms": item.latency_ms,
                }
                for item in self.case_results
            ],
        }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def aggregate_metrics(
    case_results: list[CaseResult],
    *,
    dataset_version: str,
    policy_version: str,
    prompt_version: str,
    provider: str,
    real_model_ran: bool,
    field_checks: tuple[int, int],
    missing_tp: int,
    missing_fp: int,
    missing_fn: int,
    retrieval_hits: tuple[int, int],
    citation_valid: tuple[int, int],
    routing_hits: tuple[int, int],
    approvable_hits: tuple[int, int],
    approval_boundary: tuple[int, int],
    duplicate_submission: tuple[int, int],
    limitations: list[str],
) -> EvaluationReport:
    latencies = [item.latency_ms for item in case_results if item.latency_ms is not None]
    field_ok, field_total = field_checks
    route_ok, route_total = routing_hits
    appr_ok, appr_total = approvable_hits
    ret_ok, ret_total = retrieval_hits
    cite_ok, cite_total = citation_valid
    missing_precision = missing_tp / (missing_tp + missing_fp) if (missing_tp + missing_fp) else 1.0
    missing_recall = missing_tp / (missing_tp + missing_fn) if (missing_tp + missing_fn) else 1.0
    return EvaluationReport(
        dataset_version=dataset_version,
        policy_version=policy_version,
        prompt_version=prompt_version,
        provider=provider,
        real_model_ran=real_model_ran,
        cases_total=len(case_results),
        cases_passed=sum(1 for item in case_results if item.passed),
        field_extraction_accuracy=field_ok / field_total if field_total else 0.0,
        missing_field_precision=missing_precision,
        missing_field_recall=missing_recall,
        retrieval_recall_at_k=ret_ok / ret_total if ret_total else 1.0,
        citation_validity_rate=cite_ok / cite_total if cite_total else 1.0,
        routing_accuracy=route_ok / route_total if route_total else 1.0,
        approvable_accuracy=appr_ok / appr_total if appr_total else 1.0,
        latency_ms_p50=_percentile(latencies, 50),
        latency_ms_p95=_percentile(latencies, 95),
        approval_boundary_checks_passed=approval_boundary[0],
        approval_boundary_checks_total=approval_boundary[1],
        duplicate_submission_checks_passed=duplicate_submission[0],
        duplicate_submission_checks_total=duplicate_submission[1],
        case_results=case_results,
        limitations=limitations,
    )
