from __future__ import annotations

from app.core.config import Settings
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider
from app.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider


def get_llm(settings: Settings) -> FakeLLMProvider | OllamaLLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(settings)
    return FakeLLMProvider(max_retries=settings.llm_max_retries)


def get_embedder(settings: Settings) -> FakeEmbeddingProvider | OllamaEmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    return FakeEmbeddingProvider()
