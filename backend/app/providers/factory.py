from __future__ import annotations

from app.core.config import Settings
from app.providers.azure_openai import AzureOpenAIEmbeddingProvider, AzureOpenAILLMProvider
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider
from app.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider

LLMProviderImpl = FakeLLMProvider | OllamaLLMProvider | AzureOpenAILLMProvider
EmbeddingProviderImpl = (
    FakeEmbeddingProvider | OllamaEmbeddingProvider | AzureOpenAIEmbeddingProvider
)


def get_llm(settings: Settings) -> LLMProviderImpl:
    if settings.llm_provider == "azure_openai":
        return AzureOpenAILLMProvider(settings)
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(settings)
    return FakeLLMProvider(max_retries=settings.llm_max_retries)


def get_embedder(settings: Settings) -> EmbeddingProviderImpl:
    if settings.embedding_provider == "azure_openai":
        return AzureOpenAIEmbeddingProvider(settings)
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings)
    return FakeEmbeddingProvider()
