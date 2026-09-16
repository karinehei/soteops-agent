from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InstructionChunk, InstructionDocument
from app.providers import EmbeddingProvider
from app.providers.fake import FakeEmbeddingProvider, tokenize
from app.retrieval.embedding_index import upsert_index_meta

DEFAULT_INSTRUCTIONS_PATH = Path(__file__).resolve().parents[3] / "seed" / "instructions.json"


def default_instructions_path() -> Path:
    return DEFAULT_INSTRUCTIONS_PATH


def chunk_text(body: str, *, max_chars: int = 400) -> list[str]:
    paragraphs = [part.strip() for part in body.split("\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + 1 + len(paragraph) <= max_chars:
            current = f"{current} {paragraph}"
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks or [body.strip()]


def seed_instructions(
    session: Session,
    payload: dict[str, Any],
    embedder: EmbeddingProvider | None = None,
) -> None:
    """(Re)index instruction chunks. This is the supported reindex path when switching embedders."""
    embedder = embedder or FakeEmbeddingProvider()
    for item in payload["documents"]:
        document = session.scalar(
            select(InstructionDocument).where(
                InstructionDocument.document_id == item["document_id"]
            )
        )
        valid_from = date.fromisoformat(item["valid_from"])
        valid_to = date.fromisoformat(item["valid_to"]) if item.get("valid_to") else None
        if document is None:
            document = InstructionDocument(
                id=uuid4(),
                document_id=item["document_id"],
                title=item["title"],
                version=item["version"],
                valid_from=valid_from,
                valid_to=valid_to,
                is_current=bool(item["is_current"]),
                synthetic_label=item.get("synthetic_label", "SYNTHETIC"),
                applies_to_systems=item["applies_to_systems"],
                topics=item["topics"],
                body=item["body"],
            )
            session.add(document)
            session.flush()
        else:
            document.title = item["title"]
            document.version = item["version"]
            document.valid_from = valid_from
            document.valid_to = valid_to
            document.is_current = bool(item["is_current"])
            document.synthetic_label = item.get("synthetic_label", "SYNTHETIC")
            document.applies_to_systems = item["applies_to_systems"]
            document.topics = item["topics"]
            document.body = item["body"]
            session.flush()
            existing = list(
                session.scalars(
                    select(InstructionChunk).where(InstructionChunk.document_pk == document.id)
                ).all()
            )
            for chunk in existing:
                session.delete(chunk)
            session.flush()

        parts = chunk_text(item["body"])
        vectors = embedder.embed(parts)
        for index, (text, vector) in enumerate(zip(parts, vectors, strict=True)):
            session.add(
                InstructionChunk(
                    id=uuid4(),
                    document_pk=document.id,
                    chunk_index=index,
                    source_id=f"{item['document_id']}#{index}",
                    text=text,
                    embedding=vector,
                )
            )
    upsert_index_meta(session, embedder)


def load_instructions_payload(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or "documents" not in payload:
        raise ValueError("Instructions file must contain a documents array")
    return payload


def lexical_overlap(query: str, chunk_text_value: str) -> int:
    query_tokens = set(tokenize(query))
    chunk_tokens = set(tokenize(chunk_text_value))
    return len(query_tokens & chunk_tokens)
