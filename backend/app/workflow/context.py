from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AccessRequest, PreparationRun
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider
from app.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider
from app.rules.policy import PolicyConfig

LLM = FakeLLMProvider | OllamaLLMProvider
Embedder = FakeEmbeddingProvider | OllamaEmbeddingProvider


@dataclass
class WorkflowContext:
    session: Session
    request: AccessRequest
    run: PreparationRun
    actor_id: UUID
    settings: Settings
    policy: PolicyConfig
    llm: LLM
    embedder: Embedder
