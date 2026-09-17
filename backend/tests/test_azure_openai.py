"""Azure OpenAI provider — mocked HTTP only. Not live-verified."""

from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select, text

from app.core.config import Settings
from app.core.db import create_db_engine, create_session_factory
from app.models import EMBEDDING_DIMENSION, EmbeddingIndexMeta, User
from app.providers import (
    ProviderAuthError,
    ProviderError,
    ProviderOutputError,
    ProviderTimeoutError,
)
from app.providers.azure_openai import (
    AzureOpenAIEmbeddingProvider,
    AzureOpenAILLMProvider,
    redact_secrets,
)
from app.providers.factory import get_embedder, get_llm
from app.providers.fake import FakeEmbeddingProvider, FakeLLMProvider
from app.providers.ollama import OllamaEmbeddingProvider, OllamaLLMProvider
from app.retrieval.embedding_index import (
    EmbeddingIndexIncompatibleError,
    assert_compatible,
    upsert_index_meta,
)
from app.retrieval.ingest import (
    default_instructions_path,
    load_instructions_payload,
    seed_instructions,
)
from app.schemas.requests import RequestWrite
from app.workflow.schemas import ExtractionResult
from tests.conftest import REQUESTER_EMAIL, TEST_SETTINGS, VALID_REQUEST


@pytest.fixture(autouse=True)
def _block_real_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail if a test uses the real HTTP transport instead of MockTransport."""

    def blocked(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        raise RuntimeError(f"blocked unexpected network request to {request.method} {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


def _azure_settings(**overrides: Any) -> Settings:
    base = {
        "environment": "test",
        "database_url": "postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
        "mock_integration_url": "http://127.0.0.1:8001",
        "azure_openai_enabled": True,
        "azure_openai_endpoint": "https://example.openai.azure.com/",
        "azure_openai_api_key": "test-azure-key-not-real",
        "azure_openai_chat_deployment": "demo-chat-deployment",
        "azure_openai_embedding_deployment": "demo-embed-deployment",
        "azure_openai_embedding_dimensions": EMBEDDING_DIMENSION,
        "llm_provider": "azure_openai",
        "embedding_provider": "azure_openai",
        "llm_max_retries": 2,
        "llm_timeout_seconds": 2.0,
        "demo_auth_enabled": True,
        "session_secret": "test-session-secret",
        "policy_file": str(TEST_SETTINGS.policy_file),
    }
    base.update(overrides)
    return Settings(**base)


def _extraction_payload() -> dict[str, Any]:
    return {
        "fields": {
            "employee_identifier": {
                "value": "EMP-1001",
                "excerpt": "EMP-1001",
                "ambiguous": False,
            },
            "employment_type": {"value": "vakituinen", "excerpt": "vakituinen", "ambiguous": False},
            "job_role": {
                "value": "sairaanhoitaja",
                "excerpt": "sairaanhoitaja",
                "ambiguous": False,
            },
            "unit": {"value": "demo-osasto", "excerpt": "demo-osasto", "ambiguous": False},
            "target_system": {
                "value": "demo-hr-testi",
                "excerpt": "demo-hr-testi",
                "ambiguous": False,
            },
            "requested_access_role": {
                "value": "lukuoikeus",
                "excerpt": "lukuoikeus",
                "ambiguous": False,
            },
            "start_date": {"value": "2026-10-01", "excerpt": "2026-10-01", "ambiguous": False},
            "end_date": {"value": None, "excerpt": None, "ambiguous": False},
        },
        "provider_label": "x",
        "model": "demo-chat-deployment",
        "prompt_version": "prep-v1",
    }


def _chat_response(content: str | dict[str, Any], *, finish_reason: str = "stop") -> httpx.Response:
    if isinstance(content, dict):
        body_content = json.dumps(content)
    else:
        body_content = content
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {"role": "assistant", "content": body_content},
                }
            ]
        },
    )


def _embedding_response(vectors: list[list[float]]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": [{"index": index, "embedding": vector} for index, vector in enumerate(vectors)]
        },
    )


def test_redact_secrets_masks_keys() -> None:
    text = "api-key: test-azure-key-not-real Authorization: Bearer abc.def"
    redacted = redact_secrets(text)
    assert "test-azure-key-not-real" not in redacted
    assert "abc.def" not in redacted
    assert "[REDACTED]" in redacted


def test_factory_does_not_instantiate_azure_when_fake() -> None:
    llm = get_llm(TEST_SETTINGS)
    embedder = get_embedder(TEST_SETTINGS)
    assert isinstance(llm, FakeLLMProvider)
    assert isinstance(embedder, FakeEmbeddingProvider)


def test_factory_ignores_azure_env_when_provider_is_fake() -> None:
    settings = _azure_settings(llm_provider="fake", embedding_provider="fake")
    assert isinstance(get_llm(settings), FakeLLMProvider)
    assert isinstance(get_embedder(settings), FakeEmbeddingProvider)


def test_factory_returns_azure_when_selected() -> None:
    settings = _azure_settings()
    llm = get_llm(settings)
    embedder = get_embedder(settings)
    try:
        assert isinstance(llm, AzureOpenAILLMProvider)
        assert isinstance(embedder, AzureOpenAIEmbeddingProvider)
        assert llm.model == "demo-chat-deployment"
        assert embedder.model == "demo-embed-deployment"
    finally:
        llm._client.close()
        embedder._client.close()


def test_factory_returns_ollama_when_selected() -> None:
    settings = Settings(
        environment="test",
        database_url=TEST_SETTINGS.database_url,
        mock_integration_url="http://127.0.0.1:8001",
        llm_provider="ollama",
        embedding_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        demo_auth_enabled=True,
        session_secret="test-session-secret",
    )
    llm = get_llm(settings)
    embedder = get_embedder(settings)
    try:
        assert isinstance(llm, OllamaLLMProvider)
        assert isinstance(embedder, OllamaEmbeddingProvider)
    finally:
        llm._client.close()
        embedder._client.close()


def test_missing_azure_enablement_fails_settings() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            database_url="postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
            mock_integration_url="http://127.0.0.1:8001",
            llm_provider="azure_openai",
            azure_openai_enabled=False,
            azure_openai_endpoint="https://example.openai.azure.com/",
            azure_openai_api_key="x",
            azure_openai_chat_deployment="chat",
        )
    assert "AZURE_OPENAI_ENABLED" in str(exc_info.value)


def test_azure_enabled_without_key_fails() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="test",
            database_url="postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops",
            mock_integration_url="http://127.0.0.1:8001",
            llm_provider="azure_openai",
            azure_openai_enabled=True,
            azure_openai_endpoint="https://example.openai.azure.com/",
            azure_openai_api_key=None,
            azure_openai_chat_deployment="chat",
        )
    assert "AZURE_OPENAI_API_KEY" in str(exc_info.value)


def test_valid_structured_response() -> None:
    settings = _azure_settings(llm_max_retries=0)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path.endswith("/chat/completions")
        assert request.headers.get("api-key") == "test-azure-key-not-real"
        body = json.loads(request.content.decode())
        assert body["model"] == "demo-chat-deployment"
        assert "max_completion_tokens" in body
        return _chat_response(_extraction_payload())

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, timeout=2.0)
    provider = AzureOpenAILLMProvider(settings, client=client)
    result = provider.complete_structured("extract EMP-1001", ExtractionResult, purpose="extract")
    assert result.fields["employee_identifier"].value == "EMP-1001"
    assert provider.calls == 1
    assert len(calls) == 1


def test_refusal_and_malformed_and_truncated() -> None:
    settings = _azure_settings(llm_max_retries=0)

    def refusal(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": None, "refusal": "no"},
                    }
                ]
            },
        )

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(refusal), timeout=2.0)
    )
    with pytest.raises(ProviderOutputError, match="refused"):
        provider.complete_structured("x", ExtractionResult, purpose="extract")

    def truncated(request: httpx.Request) -> httpx.Response:
        return _chat_response('{"fields":', finish_reason="length")

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(truncated), timeout=2.0)
    )
    with pytest.raises(ProviderOutputError, match="truncated|refused"):
        provider.complete_structured("x", ExtractionResult, purpose="extract")

    def malformed(request: httpx.Request) -> httpx.Response:
        return _chat_response("not-json")

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(malformed), timeout=2.0)
    )
    with pytest.raises(ProviderOutputError):
        provider.complete_structured("x", ExtractionResult, purpose="extract")

    def filtered(request: httpx.Request) -> httpx.Response:
        return _chat_response(_extraction_payload(), finish_reason="content_filter")

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(filtered), timeout=2.0)
    )
    with pytest.raises(ProviderOutputError, match="refused or truncated"):
        provider.complete_structured("x", ExtractionResult, purpose="extract")


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_do_not_retry(status: int) -> None:
    settings = _azure_settings(llm_max_retries=3)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(status, json={"error": {"message": "denied"}})

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    with pytest.raises(ProviderAuthError):
        provider.complete_structured("x", ExtractionResult, purpose="extract")
    assert calls["n"] == 1


def test_429_and_transient_retry_then_succeed() -> None:
    settings = _azure_settings(llm_max_retries=2)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": {"message": "rate"}})
        return _chat_response(_extraction_payload())

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    result = provider.complete_structured("x", ExtractionResult, purpose="extract")
    assert result.fields["employee_identifier"].value == "EMP-1001"
    assert calls["n"] == 3


def test_429_exhausts_retry_budget() -> None:
    settings = _azure_settings(llm_max_retries=1)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"message": "rate"}})

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    with pytest.raises(ProviderError, match="transient"):
        provider.complete_structured("x", ExtractionResult, purpose="extract")
    assert calls["n"] == 2


def test_timeout_exhausts_retry_budget() -> None:
    settings = _azure_settings(llm_max_retries=1)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.TimeoutException("slow")

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    with pytest.raises(ProviderTimeoutError):
        provider.complete_structured("x", ExtractionResult, purpose="extract")
    assert calls["n"] == 2


def test_unexpected_network_is_blocked_by_mock_transport() -> None:
    settings = _azure_settings(llm_max_retries=0)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network call to {request.url}")

    provider = AzureOpenAILLMProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    with pytest.raises(AssertionError, match="unexpected"):
        provider._client.post("https://example.openai.azure.com/openai/v1/chat/completions")


def test_real_http_transport_is_blocked() -> None:
    settings = _azure_settings(llm_max_retries=0)
    provider = AzureOpenAILLMProvider(settings)
    try:
        with pytest.raises(RuntimeError, match="blocked unexpected network"):
            provider.complete_structured("x", ExtractionResult, purpose="extract")
    finally:
        provider._client.close()


def test_embedding_request_uses_deployment_and_dimensions() -> None:
    settings = _azure_settings(llm_max_retries=0)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path.endswith("/embeddings")
        assert request.headers.get("api-key") == "test-azure-key-not-real"
        body = json.loads(request.content.decode())
        assert body["model"] == "demo-embed-deployment"
        assert body["dimensions"] == EMBEDDING_DIMENSION
        return _embedding_response([[0.02] * EMBEDDING_DIMENSION])

    provider = AzureOpenAIEmbeddingProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    vectors = provider.embed(["synteettinen"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSION
    assert len(calls) == 1


def test_embedding_dimension_mismatch() -> None:
    settings = _azure_settings(llm_max_retries=0)

    def handler(request: httpx.Request) -> httpx.Response:
        return _embedding_response([[0.1] * 8])

    provider = AzureOpenAIEmbeddingProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    )
    with pytest.raises(ProviderOutputError, match="dimension mismatch"):
        provider.embed(["synteettinen"])


def test_embedding_config_dimension_must_match_index() -> None:
    with pytest.raises(ValueError, match="incompatible with the fixed index dimension"):
        AzureOpenAIEmbeddingProvider(
            _azure_settings(azure_openai_embedding_dimensions=1536),
            client=httpx.Client(
                transport=httpx.MockTransport(lambda r: httpx.Response(500)), timeout=2.0
            ),
        )


def test_embedding_index_incompatible(isolated_db: None) -> None:
    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            fake = FakeEmbeddingProvider()
            upsert_index_meta(session, fake)
            session.commit()

            azure = MagicMock()
            azure.name = "azure_openai"
            azure.model = "demo-embed-deployment"
            azure.dimension = EMBEDDING_DIMENSION
            with pytest.raises(EmbeddingIndexIncompatibleError, match="re-run soteops-seed"):
                assert_compatible(session, azure)
    finally:
        engine.dispose()


def test_exceptions_and_logs_do_not_leak_api_key(caplog: pytest.LogCaptureFixture) -> None:
    settings = _azure_settings(llm_max_retries=0)
    secret = "test-azure-key-not-real"
    prompt = "EMP-1001 lukuoikeus with api-key=test-azure-key-not-real"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("failed api-key=test-azure-key-not-real")

    with caplog.at_level(logging.DEBUG):
        provider = AzureOpenAILLMProvider(
            settings, client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
        )
        with pytest.raises(ProviderError) as exc_info:
            provider.complete_structured(prompt, ExtractionResult, purpose="extract")
    message = str(exc_info.value)
    assert secret not in message
    assert "EMP-1001" not in message
    log_text = " ".join(record.getMessage() for record in caplog.records)
    assert secret not in log_text


def test_mocked_end_to_end_prepare_with_azure(isolated_db: None) -> None:
    settings = _azure_settings(llm_max_retries=0)
    vector = [0.01] * EMBEDDING_DIMENSION

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/chat/completions"):
            body = json.loads(request.content.decode())
            purpose_hint = body["messages"][-1]["content"]
            schema_name = body.get("response_format", {}).get("json_schema", {}).get("name", "")
            if schema_name == "ExplanationResult" or "Write a Finnish explanation" in purpose_hint:
                return _chat_response(
                    {
                        "explanation_text": "Synteettinen Azure-mock selitys.",
                        "clarification_draft": "",
                        "cited_source_ids": [],
                        "evidence_missing": False,
                        "provider_label": "Azure OpenAI",
                        "model": "demo-chat-deployment",
                        "prompt_version": "prep-v1",
                    }
                )
            return _chat_response(_extraction_payload())
        if path.endswith("/embeddings"):
            body = json.loads(request.content.decode())
            count = len(body["input"]) if isinstance(body["input"], list) else 1
            return _embedding_response([vector for _ in range(count)])
        raise AssertionError(f"unexpected path {path}")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2.0)
    llm = AzureOpenAILLMProvider(settings, client=client)
    embedder = AzureOpenAIEmbeddingProvider(settings, client=client)

    engine = create_db_engine(TEST_SETTINGS.database_url)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            session.execute(text("DELETE FROM embedding_index_meta"))
            session.execute(text("DELETE FROM instruction_chunks"))
            session.commit()
            seed_instructions(
                session,
                load_instructions_payload(default_instructions_path()),
                embedder=embedder,
            )
            session.commit()
            meta = session.scalar(select(EmbeddingIndexMeta).where(EmbeddingIndexMeta.id == 1))
            assert meta is not None
            assert meta.provider == "azure_openai"
            assert meta.model == "demo-embed-deployment"

            requester = session.scalar(select(User).where(User.email == REQUESTER_EMAIL))
            assert requester is not None
            from uuid import uuid4

            from app.models import AccessRequest, Approval, RequestStatus, Submission
            from app.rules.policy import current_policy
            from app.services.proposals import prepare_proposal

            payload = RequestWrite(**VALID_REQUEST)
            request = AccessRequest(
                id=uuid4(),
                owner_id=requester.id,
                original_text=payload.original_text,
                revision=1,
                status=RequestStatus.SUBMITTED,
                start_date=payload.start_date,
                end_date=payload.end_date,
                employee_identifier=payload.employee_identifier,
                employment_type=payload.employment_type,
                job_role=payload.job_role,
                unit=payload.unit,
                target_system=payload.target_system,
                requested_access_role=payload.requested_access_role,
            )
            session.add(request)
            session.flush()
            proposal = prepare_proposal(
                session,
                request,
                requester.id,
                policy=current_policy(),
                settings=settings,
                llm=llm,
                embedder=embedder,
            )
            session.commit()
            session.refresh(request)
            assert proposal.extracted_fields.get("employee_identifier") == "EMP-1001"
            assert proposal.provider_metadata.get("llm_provider") == "azure_openai"
            assert request.status in {
                RequestStatus.READY_FOR_REVIEW,
                RequestStatus.NEEDS_CLARIFICATION,
            }
            assert (
                session.scalar(select(Approval.id).where(Approval.request_id == request.id)) is None
            )
            assert (
                session.scalar(select(Submission.id).where(Submission.request_id == request.id))
                is None
            )
            # Restore fake index so other suites (session-scoped seed) stay compatible.
            seed_instructions(
                session,
                load_instructions_payload(default_instructions_path()),
                embedder=FakeEmbeddingProvider(),
            )
            session.commit()
    finally:
        engine.dispose()


def test_fake_and_ollama_unchanged_labels() -> None:
    from app.providers import FAKE_PROVIDER_LABEL, OLLAMA_PROVIDER_LABEL

    assert "ei mitattua" in FAKE_PROVIDER_LABEL.lower()
    assert "ollama" in OLLAMA_PROVIDER_LABEL.lower()
    fake = FakeLLMProvider()
    assert (
        fake.complete_structured(
            "EMP-1001 lukuoikeus demo-hr-testi 2026-10-01", ExtractionResult, purpose="extract"
        )
        .fields["employee_identifier"]
        .value
        == "EMP-1001"
    )
