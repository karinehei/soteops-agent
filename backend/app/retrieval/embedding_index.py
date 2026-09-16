"""Embedding index configuration tracking — prevents mixing providers/deployments."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmbeddingIndexMeta
from app.providers import EmbeddingProvider


class EmbeddingIndexIncompatibleError(ValueError):
    """Indexed vectors were produced by a different embedding configuration."""


@dataclass(frozen=True)
class EmbeddingFingerprint:
    provider: str
    model: str
    dimension: int

    @classmethod
    def from_provider(cls, embedder: EmbeddingProvider) -> EmbeddingFingerprint:
        return cls(provider=embedder.name, model=embedder.model, dimension=embedder.dimension)


def get_index_meta(session: Session) -> EmbeddingIndexMeta | None:
    return session.scalar(select(EmbeddingIndexMeta).where(EmbeddingIndexMeta.id == 1))


def assert_compatible(session: Session, embedder: EmbeddingProvider) -> None:
    meta = get_index_meta(session)
    if meta is None:
        return
    expected = EmbeddingFingerprint.from_provider(embedder)
    if (
        meta.provider != expected.provider
        or meta.model != expected.model
        or meta.dimension != expected.dimension
    ):
        raise EmbeddingIndexIncompatibleError(
            "Instruction embeddings were indexed with "
            f"provider={meta.provider!r} model={meta.model!r} dimension={meta.dimension}, "
            f"but the current embedder is provider={expected.provider!r} "
            f"model={expected.model!r} dimension={expected.dimension}. "
            "Do not mix embeddings. Truncate instruction_chunks / embedding_index_meta and "
            "re-run soteops-seed with the target embedder (see docs/azure-openai.md). "
            "Automatic reindex is not performed."
        )


def upsert_index_meta(session: Session, embedder: EmbeddingProvider) -> None:
    fingerprint = EmbeddingFingerprint.from_provider(embedder)
    meta = get_index_meta(session)
    if meta is None:
        session.add(
            EmbeddingIndexMeta(
                id=1,
                provider=fingerprint.provider,
                model=fingerprint.model,
                dimension=fingerprint.dimension,
            )
        )
    else:
        meta.provider = fingerprint.provider
        meta.model = fingerprint.model
        meta.dimension = fingerprint.dimension
    session.flush()
