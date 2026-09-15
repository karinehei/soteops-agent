from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, load_settings
from app.models import AccessRequest, PreparationRun, PreparationRunStatus, Proposal, RequestStatus
from app.providers import PROMPT_VERSION, ProviderError
from app.providers.factory import get_embedder, get_llm
from app.rules.policy import PolicyConfig, current_policy
from app.rules.transitions import ensure_transition
from app.services.audit import record_audit
from app.workflow.context import WorkflowContext
from app.workflow.graph import GRAPH_NODES, build_preparation_graph
from app.workflow.nodes import persist_failure, workflow_ctx
from app.workflow.schemas import PrepState

_GRAPH = None


def _graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_preparation_graph()
    return _GRAPH


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def request_fields(request: AccessRequest) -> dict[str, Any]:
    return {
        "employee_identifier": request.employee_identifier,
        "employment_type": request.employment_type,
        "job_role": request.job_role,
        "unit": request.unit,
        "target_system": request.target_system,
        "requested_access_role": request.requested_access_role,
        "start_date": _iso(request.start_date),
        "end_date": _iso(request.end_date),
    }


def build_excerpts(original_text: str, fields: dict[str, Any]) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for key, value in fields.items():
        if isinstance(value, str) and value and value in original_text:
            excerpts[key] = value
    return excerpts


def interrupt_stale_runs(session: Session, request_id: UUID, actor_id: UUID) -> None:
    runs = session.scalars(
        select(PreparationRun).where(
            PreparationRun.request_id == request_id,
            PreparationRun.status == PreparationRunStatus.RUNNING,
        )
    ).all()
    for run in runs:
        run.status = PreparationRunStatus.INTERRUPTED
        record_audit(
            session,
            event_type="preparation_interrupted",
            actor_id=actor_id,
            request_id=request_id,
            metadata={
                "revision": run.revision,
                "node": run.current_node,
                "run_status": PreparationRunStatus.INTERRUPTED.value,
            },
        )
    session.flush()


def prepare_proposal(
    session: Session,
    request: AccessRequest,
    actor_id: UUID,
    policy: PolicyConfig | None = None,
    settings: Settings | None = None,
    llm: Any = None,
    embedder: Any = None,
) -> Proposal:
    policy = policy or current_policy()
    settings = settings or load_settings()
    llm = llm or get_llm(settings)
    embedder = embedder or get_embedder(settings)

    ensure_transition(request.status, RequestStatus.PREPARING)
    request.status = RequestStatus.PREPARING

    if request.current_proposal_id is not None:
        previous = session.get(Proposal, request.current_proposal_id)
        if previous is not None and previous.invalidated_at is None:
            previous.invalidated_at = datetime.now(UTC)
            record_audit(
                session,
                event_type="proposal_invalidated",
                actor_id=actor_id,
                request_id=request.id,
                metadata={"revision": previous.revision, "proposal_id": str(previous.id)},
            )

    interrupt_stale_runs(session, request.id, actor_id)
    run = PreparationRun(
        id=uuid4(),
        request_id=request.id,
        revision=request.revision,
        current_node="start",
        status=PreparationRunStatus.RUNNING,
        error_category=None,
        provider_name=llm.name,
        model=llm.model,
        prompt_version=PROMPT_VERSION,
        embedding_provider=embedder.name,
        durable_resume=False,
    )
    session.add(run)
    session.flush()

    initial = PrepState(
        request_id=str(request.id),
        revision=request.revision,
        original_text=request.original_text,
        form_fields=request_fields(request),
        provider_metadata={
            "llm_provider": llm.name,
            "llm_label": llm.label,
            "prompt_version": PROMPT_VERSION,
            "embedding_provider": embedder.name,
            "fake_output": llm.name == "fake",
            "measured_performance": False,
            "durable_graph_resume": False,
            "graph_nodes": list(GRAPH_NODES),
        },
    )
    token = workflow_ctx.set(
        WorkflowContext(
            session=session,
            request=request,
            run=run,
            actor_id=actor_id,
            settings=settings,
            policy=policy,
            llm=llm,
            embedder=embedder,
        )
    )
    try:
        _graph().invoke(initial.model_dump())
        run.status = PreparationRunStatus.COMPLETED
        run.current_node = "persist_proposal_or_clarification"
        session.flush()
    except ProviderError as exc:
        run.status = PreparationRunStatus.FAILED
        run.error_category = exc.category
        persist_failure(initial, exc)
        session.flush()
    finally:
        workflow_ctx.reset(token)

    proposal = session.get(Proposal, request.current_proposal_id)
    if proposal is None:
        raise RuntimeError("preparation did not persist a proposal")
    return proposal
