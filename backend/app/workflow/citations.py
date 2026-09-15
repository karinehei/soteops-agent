from __future__ import annotations

from typing import Any


def validate_citation_membership(
    cited_source_ids: list[str],
    retrieved: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep citations that appear in this retrieval set.

    A valid source_id only proves membership. It does not prove that the
    passage factually supports the model's claim.
    """
    allowed = {item["source_id"]: item for item in retrieved}
    kept: list[dict[str, Any]] = []
    invented: list[str] = []
    seen: set[str] = set()
    for source_id in cited_source_ids:
        if source_id in allowed and source_id not in seen:
            kept.append(allowed[source_id])
            seen.add(source_id)
        elif source_id not in allowed:
            invented.append(source_id)
    return kept, invented
