from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

CaseSplit = Literal["train", "held_out"]
CaseCategory = Literal[
    "complete",
    "missing_fields",
    "prohibited",
    "ambiguous",
    "evidence",
    "prompt_injection",
    "integration",
]
EvalMode = Literal["pipeline", "retrieval", "rules"]

DATASET_VERSION = "eval-v1"


@dataclass(frozen=True)
class CaseInput:
    original_text: str
    form_fields: dict[str, Any]


@dataclass(frozen=True)
class RetrievalSpec:
    query: str
    target_system: str | None
    as_of: date
    top_k: int


@dataclass(frozen=True)
class CaseExpectation:
    extracted_fields: dict[str, Any]
    missing_fields: list[str]
    violation_codes: list[str]
    status: str | None
    approvable: bool | None
    retrieval_document_ids: list[str]
    retrieval_must_exclude: list[str]


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    split: CaseSplit
    category: CaseCategory
    eval_mode: EvalMode
    label: str
    input: CaseInput
    retrieval: RetrievalSpec | None
    expected: CaseExpectation
    notes: str


def default_cases_path() -> Path:
    return Path(__file__).resolve().parents[3] / "seed" / "evaluation" / "cases.json"


def load_cases(path: Path | None = None) -> list[EvaluationCase]:
    resolved = path or default_cases_path()
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if payload.get("version") != DATASET_VERSION:
        raise ValueError(f"Expected dataset version {DATASET_VERSION}")
    cases: list[EvaluationCase] = []
    for raw in payload["cases"]:
        retrieval = None
        if "retrieval" in raw and raw["retrieval"]:
            r = raw["retrieval"]
            retrieval = RetrievalSpec(
                query=r["query"],
                target_system=r.get("target_system"),
                as_of=date.fromisoformat(r["as_of"]),
                top_k=int(r.get("top_k", 4)),
            )
        exp = raw["expected"]
        cases.append(
            EvaluationCase(
                id=raw["id"],
                split=raw["split"],
                category=raw["category"],
                eval_mode=raw.get("eval_mode", "pipeline"),
                label=raw["label"],
                input=CaseInput(
                    original_text=raw["input"]["original_text"],
                    form_fields=dict(raw["input"].get("form_fields") or {}),
                ),
                retrieval=retrieval,
                expected=CaseExpectation(
                    extracted_fields=dict(exp.get("extracted_fields") or {}),
                    missing_fields=list(exp.get("missing_fields") or []),
                    violation_codes=list(exp.get("violation_codes") or []),
                    status=exp.get("status"),
                    approvable=exp.get("approvable"),
                    retrieval_document_ids=list(exp.get("retrieval_document_ids") or []),
                    retrieval_must_exclude=list(exp.get("retrieval_must_exclude") or []),
                ),
                notes=raw.get("notes", ""),
            )
        )
    return cases


def filter_cases(
    cases: list[EvaluationCase],
    *,
    split: CaseSplit | None = None,
    category: CaseCategory | None = None,
) -> list[EvaluationCase]:
    result = cases
    if split is not None:
        result = [case for case in result if case.split == split]
    if category is not None:
        result = [case for case in result if case.category == category]
    return result
