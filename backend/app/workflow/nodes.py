from __future__ import annotations

from contextvars import ContextVar
from datetime import date
from typing import Any
from uuid import uuid4

from app.models import AccessRequest, Proposal, RequestStatus
from app.providers import PROMPT_VERSION, ProviderError
from app.retrieval.retrieve import retrieve_instructions
from app.rules.engine import evaluate_rules, is_approvable
from app.rules.hashing import payload_hash
from app.rules.transitions import ensure_transition
from app.services.audit import record_audit
from app.workflow.citations import validate_citation_membership
from app.workflow.context import WorkflowContext
from app.workflow.prompts import EXPLAIN_PROMPT, EXTRACT_PROMPT, UNTRUSTED_NOTICE, retrieved_block
from app.workflow.schemas import EXTRACT_FIELD_NAMES, ExplanationResult, ExtractionResult, PrepState

workflow_ctx: ContextVar[WorkflowContext] = ContextVar("workflow_ctx")


def _coerce(state: Any) -> PrepState:
    return state if isinstance(state, PrepState) else PrepState.model_validate(state)


def _ctx() -> WorkflowContext:
    return workflow_ctx.get()


def _mark(node: str) -> None:
    context = _ctx()
    context.run.current_node = node
    context.session.flush()
    record_audit(
        context.session,
        event_type="preparation_node",
        actor_id=context.actor_id,
        request_id=context.request.id,
        metadata={"node": node, "provider": context.llm.name, "revision": context.request.revision},
    )


def extract_fields(state: PrepState) -> dict[str, Any]:
    state = _coerce(state)
    _mark("extract_fields")
    context = _ctx()
    prompt = EXTRACT_PROMPT.format(
        notice=UNTRUSTED_NOTICE,
        prompt_version=PROMPT_VERSION,
        original_text=state.original_text,
        form_fields=state.form_fields,
    )
    result = context.llm.complete_structured(prompt, ExtractionResult, purpose="extract")
    return {
        "current_node": "extract_fields",
        "extracted_fields": {
            name: (result.fields[name].model_dump() if name in result.fields else None)
            for name in EXTRACT_FIELD_NAMES
        },
        "provider_metadata": {
            "llm_provider": context.llm.name,
            "llm_model": result.model,
            "llm_label": result.provider_label,
            "prompt_version": result.prompt_version,
            "embedding_provider": context.embedder.name,
            "embedding_model": context.embedder.model,
            "fake_output": context.llm.name == "fake",
            "measured_performance": False,
            "durable_graph_resume": False,
        },
    }


def validate_extracted_fields(state: PrepState) -> dict[str, Any]:
    state = _coerce(state)
    _mark("validate_extracted_fields")
    original = state.original_text
    original_lower = original.lower()
    values: dict[str, Any] = {}
    excerpts: dict[str, Any] = {}
    for name in EXTRACT_FIELD_NAMES:
        form_value = state.form_fields.get(name)
        raw = state.extracted_fields.get(name) or {}
        extracted_value = raw.get("value") if isinstance(raw, dict) else None
        ambiguous = bool(raw.get("ambiguous")) if isinstance(raw, dict) else False
        excerpt = raw.get("excerpt") if isinstance(raw, dict) else None
        chosen: Any = None
        if form_value not in (None, ""):
            chosen = form_value if not isinstance(form_value, date) else form_value.isoformat()
        elif extracted_value and not ambiguous and str(extracted_value).lower() in original_lower:
            chosen = extracted_value
        else:
            chosen = None
        if name in {"start_date", "end_date"}:
            parsed = _parse_date(chosen)
            chosen = parsed.isoformat() if isinstance(parsed, date) else None
        values[name] = chosen
        if excerpt and str(excerpt).lower() in original_lower:
            excerpts[name] = excerpt
        elif chosen and str(chosen).lower() in original_lower:
            excerpts[name] = str(chosen)
    missing, violations = evaluate_rules(values, _ctx().policy)
    return {
        "current_node": "validate_extracted_fields",
        "extracted_fields": values,
        "excerpts": excerpts,
        "missing_fields": missing,
        "rule_violations": violations,
    }


def retrieve_instructions_node(state: PrepState) -> dict[str, Any]:
    state = _coerce(state)
    _mark("retrieve_instructions")
    context = _ctx()
    query = " ".join(
        part
        for part in [
            state.original_text,
            str(state.extracted_fields.get("target_system") or ""),
            str(state.extracted_fields.get("requested_access_role") or ""),
            str(state.extracted_fields.get("job_role") or ""),
        ]
        if part
    )
    retrieved = retrieve_instructions(
        context.session,
        query=query,
        target_system=state.extracted_fields.get("target_system"),
        top_k=context.settings.retrieval_top_k,
        embed_query=context.embedder.embed([query])[0],
    )
    record_audit(
        context.session,
        event_type="instructions_retrieved",
        actor_id=context.actor_id,
        request_id=context.request.id,
        metadata={
            "revision": context.request.revision,
            "source_ids": [item["source_id"] for item in retrieved],
            "provider": context.embedder.name,
        },
    )
    return {
        "current_node": "retrieve_instructions",
        "retrieved": retrieved,
        "evidence_missing": not retrieved,
    }


def explain_findings(state: PrepState) -> dict[str, Any]:
    state = _coerce(state)
    _mark("explain_findings")
    context = _ctx()
    prompt = EXPLAIN_PROMPT.format(
        notice=UNTRUSTED_NOTICE,
        prompt_version=PROMPT_VERSION,
        missing_fields=state.missing_fields,
        violations=state.rule_violations,
        retrieved_block=retrieved_block(state.retrieved),
    )
    result = context.llm.complete_structured(prompt, ExplanationResult, purpose="explain")
    return {
        "current_node": "explain_findings",
        "explanation_text": result.explanation_text,
        "clarification_draft": result.clarification_draft,
        "source_references": [{"source_id": item} for item in result.cited_source_ids],
        "evidence_missing": result.evidence_missing or state.evidence_missing,
        "provider_metadata": {
            **state.provider_metadata,
            "explain_model": result.model,
            "explain_label": result.provider_label,
        },
    }


def validate_citations(state: PrepState) -> dict[str, Any]:
    state = _coerce(state)
    _mark("validate_citations")
    cited = [
        str(item["source_id"])
        for item in state.source_references
        if isinstance(item, dict) and item.get("source_id")
    ]
    kept, invented = validate_citation_membership(cited, state.retrieved)
    explanation = state.explanation_text
    evidence_missing = state.evidence_missing
    if invented:
        explanation = (
            f"{explanation} Keksityt viitteet poistettiin mekaanisesti: {', '.join(invented)}. "
            "Kelvollinen tunniste ei todista, että kohta tukee väitettä."
        )
    if not kept:
        evidence_missing = True
        if "Ei tuettua vastausta" not in explanation:
            explanation = (
                f"{explanation} Voimassa olevaa ohjenäyttöä ei jäänyt jäljelle. "
                "Ei tuettua vastausta."
            )
    return {
        "current_node": "validate_citations",
        "source_references": kept,
        "invented_citations": invented,
        "explanation_text": explanation,
        "evidence_missing": evidence_missing,
    }


def persist_proposal_or_clarification(state: PrepState) -> dict[str, Any]:
    state = _coerce(state)
    _mark("persist_proposal_or_clarification")
    context = _ctx()
    request = context.request
    _apply_extracted_to_request(request, state.extracted_fields)
    downstream = {
        "employee_identifier": request.employee_identifier,
        "target_system": request.target_system,
        "requested_access_role": request.requested_access_role,
        "start_date": _iso(request.start_date),
        "end_date": _iso(request.end_date),
        "revision": request.revision,
        "policy_version": context.policy.version,
    }
    next_status = (
        RequestStatus.READY_FOR_REVIEW
        if is_approvable(state.missing_fields, state.rule_violations)
        else RequestStatus.NEEDS_CLARIFICATION
    )
    ensure_transition(request.status, next_status)
    proposal = Proposal(
        id=uuid4(),
        request_id=request.id,
        revision=request.revision,
        extracted_fields=state.extracted_fields,
        excerpts=state.excerpts,
        missing_fields=state.missing_fields,
        rule_violations=state.rule_violations,
        explanation_text=state.explanation_text,
        clarification_draft=state.clarification_draft,
        source_references=_source_references_for_reviewer(state)
        + [{"policy_version": context.policy.version, "source": context.policy.source}],
        provider_metadata={
            **state.provider_metadata,
            "evidence_missing": state.evidence_missing,
            "invented_citations": state.invented_citations,
            "not_authorization": True,
        },
        downstream_payload=downstream,
        policy_version=context.policy.version,
        payload_hash=payload_hash(downstream),
    )
    context.session.add(proposal)
    context.session.flush()
    request.current_proposal_id = proposal.id
    request.status = next_status
    context.run.current_node = "persist_proposal_or_clarification"
    context.session.flush()
    record_audit(
        context.session,
        event_type="proposal_prepared",
        actor_id=context.actor_id,
        request_id=request.id,
        metadata={
            "revision": request.revision,
            "proposal_id": str(proposal.id),
            "status": next_status.value,
            "missing_fields": state.missing_fields,
            "violation_codes": [item["code"] for item in state.rule_violations],
            "policy_version": context.policy.version,
            "provider": context.llm.name,
        },
    )
    return {"current_node": "persist_proposal_or_clarification"}


def _source_references_for_reviewer(state: PrepState) -> list[dict[str, Any]]:
    """Store membership-checked citations, or retrieved evidence if the model cited none."""
    if state.source_references:
        return list(state.source_references)
    return list(state.retrieved)


def persist_failure(state: PrepState, error: ProviderError) -> None:
    context = _ctx()
    request = context.request
    missing, violations = evaluate_rules(
        state.extracted_fields or state.form_fields, context.policy
    )
    explanation = (
        f"{context.llm.label}. Valmistelu keskeytyi ({error.category}). "
        "Tämä ei ole mitattu mallisuorituskyky. Ihmisen on täydennettävä hakemus. "
        "Graafilla ei ole kestävää palautusta; uudelleenyritys alkaa alusta."
    )
    ensure_transition(request.status, RequestStatus.NEEDS_CLARIFICATION)
    proposal = Proposal(
        id=uuid4(),
        request_id=request.id,
        revision=request.revision,
        extracted_fields=state.extracted_fields or {},
        excerpts=state.excerpts,
        missing_fields=missing,
        rule_violations=violations,
        explanation_text=explanation,
        clarification_draft=(
            "Yritä uudelleen täydennettynä. Valmistelu ei saa hyväksyntää eikä integraatiokutsua."
        ),
        source_references=[
            {"policy_version": context.policy.version, "source": context.policy.source}
        ],
        provider_metadata={
            "llm_provider": context.llm.name,
            "llm_label": context.llm.label,
            "error_category": error.category,
            "fake_output": context.llm.name == "fake",
            "measured_performance": False,
            "durable_graph_resume": False,
        },
        downstream_payload={
            "revision": request.revision,
            "policy_version": context.policy.version,
        },
        policy_version=context.policy.version,
        payload_hash=payload_hash(
            {"revision": request.revision, "policy_version": context.policy.version}
        ),
    )
    context.session.add(proposal)
    context.session.flush()
    request.current_proposal_id = proposal.id
    request.status = RequestStatus.NEEDS_CLARIFICATION
    record_audit(
        context.session,
        event_type="preparation_failed",
        actor_id=context.actor_id,
        request_id=request.id,
        metadata={
            "revision": request.revision,
            "status": RequestStatus.NEEDS_CLARIFICATION.value,
            "provider": context.llm.name,
            "run_status": "failed",
        },
    )


def _apply_extracted_to_request(request: AccessRequest, values: dict[str, Any]) -> None:
    mapping = {
        "employee_identifier": values.get("employee_identifier"),
        "employment_type": values.get("employment_type"),
        "job_role": values.get("job_role"),
        "unit": values.get("unit"),
        "target_system": values.get("target_system"),
        "requested_access_role": values.get("requested_access_role"),
        "start_date": _parse_date(values.get("start_date")),
        "end_date": _parse_date(values.get("end_date")),
    }
    for key, value in mapping.items():
        current = getattr(request, key)
        if current in (None, "") and value not in (None, ""):
            setattr(request, key, value)


def _parse_date(value: Any) -> date | str | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
