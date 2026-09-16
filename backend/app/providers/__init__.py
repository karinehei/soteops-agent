"""LLM and embedding provider contracts."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

PROMPT_VERSION = "prep-v1"
FAKE_PROVIDER_LABEL = "SYNTEETTINEN FAKE-TARJOAJA — ei mitattua mallisuorituskykyä"
FAKE_MODEL = "fake-prep-v1"
OLLAMA_PROVIDER_LABEL = "Paikallinen Ollama — ei tuotantokäyttöä, ei kalibroitua todennäköisyyttä"


class ProviderError(Exception):
    category = "provider_error"


class ProviderTimeoutError(ProviderError):
    category = "timeout"


class ProviderOutputError(ProviderError):
    category = "invalid_structured_output"


class ProviderAuthError(ProviderError):
    category = "auth_error"


class LLMProvider(Protocol):
    name: str
    model: str
    version: str
    label: str

    def complete_structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        purpose: str,
    ) -> T: ...


class EmbeddingProvider(Protocol):
    name: str
    model: str
    version: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
