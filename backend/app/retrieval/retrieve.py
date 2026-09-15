from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import InstructionChunk, InstructionDocument
from app.providers.fake import hashed_embedding
from app.retrieval.ingest import lexical_overlap


def retrieve_instructions(
    session: Session,
    *,
    query: str,
    target_system: str | None,
    top_k: int,
    as_of: date | None = None,
    embed_query: list[float] | None = None,
) -> list[dict[str, Any]]:
    as_of = as_of or date.today()
    vector = embed_query or hashed_embedding(query)
    rows = (
        session.execute(
            select(InstructionChunk)
            .options(joinedload(InstructionChunk.document))
            .join(InstructionDocument)
            .where(InstructionDocument.valid_from <= as_of)
            .where(
                (InstructionDocument.valid_to.is_(None)) | (InstructionDocument.valid_to >= as_of)
            )
        )
        .unique()
        .scalars()
        .all()
    )

    scored: list[tuple[float, InstructionChunk]] = []
    for chunk in rows:
        systems = list(chunk.document.applies_to_systems)
        if target_system and "*" not in systems and target_system not in systems:
            continue
        lexical = lexical_overlap(query, f"{chunk.document.title} {chunk.text}")
        cosine = _cosine(vector, list(chunk.embedding))
        # Rank only. Do not treat this as a calibrated probability.
        rank_score = float(lexical) + cosine
        if lexical == 0 and cosine < 0.05:
            continue
        scored.append((rank_score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    seen_documents: set[str] = set()
    results: list[dict[str, Any]] = []
    for _, chunk in scored:
        document_id = chunk.document.document_id
        if document_id in seen_documents:
            continue
        seen_documents.add(document_id)
        results.append(
            {
                "source_id": chunk.source_id,
                "document_id": document_id,
                "title": chunk.document.title,
                "version": chunk.document.version,
                "excerpt": chunk.text,
                "synthetic_label": chunk.document.synthetic_label,
                "valid_from": chunk.document.valid_from.isoformat(),
                "valid_to": chunk.document.valid_to.isoformat()
                if chunk.document.valid_to
                else None,
                "is_current": chunk.document.is_current,
            }
        )
        if len(results) >= top_k:
            break
    return results


def _cosine(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))
