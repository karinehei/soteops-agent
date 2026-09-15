from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

EXTRACT_FIELD_NAMES = (
    "employee_identifier",
    "employment_type",
    "job_role",
    "unit",
    "target_system",
    "requested_access_role",
    "start_date",
    "end_date",
)


class FieldValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    excerpt: str | None = None
    ambiguous: bool = False


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, FieldValue]
    provider_label: str
    model: str
    prompt_version: str


class ExplanationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_text: str
    clarification_draft: str = ""
    cited_source_ids: list[str] = Field(default_factory=list)
    evidence_missing: bool = False
    provider_label: str
    model: str
    prompt_version: str


class PrepState(BaseModel):
    """In-memory graph state. Not a durable checkpoint."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    revision: int
    original_text: str
    form_fields: dict[str, Any]
    current_node: str = "start"
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    excerpts: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    rule_violations: list[dict[str, str]] = Field(default_factory=list)
    retrieved: list[dict[str, Any]] = Field(default_factory=list)
    explanation_text: str = ""
    clarification_draft: str = ""
    source_references: list[dict[str, Any]] = Field(default_factory=list)
    evidence_missing: bool = False
    invented_citations: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    error_category: str | None = None
