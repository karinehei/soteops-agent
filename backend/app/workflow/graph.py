from __future__ import annotations

from typing import Any

from app.workflow.nodes import (
    explain_findings,
    extract_fields,
    persist_proposal_or_clarification,
    retrieve_instructions_node,
    validate_citations,
    validate_extracted_fields,
)
from app.workflow.schemas import PrepState

GRAPH_NODES = (
    "extract_fields",
    "validate_extracted_fields",
    "retrieve_instructions",
    "explain_findings",
    "validate_citations",
    "persist_proposal_or_clarification",
)


def build_preparation_graph() -> Any:
    from langgraph.graph import END, START, StateGraph

    graph: StateGraph[PrepState] = StateGraph(PrepState)
    graph.add_node("extract_fields", extract_fields)
    graph.add_node("validate_extracted_fields", validate_extracted_fields)
    graph.add_node("retrieve_instructions", retrieve_instructions_node)
    graph.add_node("explain_findings", explain_findings)
    graph.add_node("validate_citations", validate_citations)
    graph.add_node("persist_proposal_or_clarification", persist_proposal_or_clarification)
    graph.add_edge(START, "extract_fields")
    graph.add_edge("extract_fields", "validate_extracted_fields")
    graph.add_edge("validate_extracted_fields", "retrieve_instructions")
    graph.add_edge("retrieve_instructions", "explain_findings")
    graph.add_edge("explain_findings", "validate_citations")
    graph.add_edge("validate_citations", "persist_proposal_or_clarification")
    graph.add_edge("persist_proposal_or_clarification", END)
    return graph.compile()
