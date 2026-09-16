# Azure OpenAI provider adapter

**Maturity**

| Claim | Status |
| --- | --- |
| Adapter code in tree | **Implemented** |
| Unit / integration tests with mocked Azure HTTP | **Tested locally with mocked Azure responses** |
| Calls against a real Azure OpenAI resource | **Not live-verified** |
| Managed identity / Entra token auth | **Not implemented** (documented future only) |

Fake-provider evaluation metrics are **not** Azure model quality. CI and Compose remain on `LLM_PROVIDER=fake` / `EMBEDDING_PROVIDER=fake` unless you explicitly opt in.

## Documentation verification (2026-09-16)

Contract used by this adapter:

| Concern | Choice | Source |
| --- | --- | --- |
| Base URL | `{AZURE_OPENAI_ENDPOINT}/openai/v1` (endpoint may already include `/openai/v1`) | [v1 API lifecycle](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle) |
| Chat | `POST .../chat/completions`, `model` = **chat deployment name** | [Chat completions](https://learn.microsoft.com/en-us/azure/foundry/openai/latest) |
| Embeddings | `POST .../embeddings`, `model` = **embedding deployment name** | [Embeddings REST](https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/embeddings), [How to embeddings](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/embeddings) |
| Auth (this slice) | `api-key` header from `AZURE_OPENAI_API_KEY` | Same docs (API key path) |
| Structured output | `response_format.json_schema` + local Pydantic validation | Chat completions `response_format` |
| Embedding size | Request `dimensions` = index size (`64`); reject mismatches | Index is `Vector(64)` |

Managed identity / `DefaultAzureCredential` is **not** wired. Future work only.

## Enablement (explicit)

All of the following are required — missing config fails validation; there is **no** fallback to fake/ollama:

```bash
AZURE_OPENAI_ENABLED=true
LLM_PROVIDER=azure_openai          # and/or EMBEDDING_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=YOUR_KEY      # env only — never commit
AZURE_OPENAI_CHAT_DEPLOYMENT=your-chat-deployment
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your-embed-deployment
# Optional; must equal the fixed index dimension (64) or the adapter refuses to start:
AZURE_OPENAI_EMBEDDING_DIMENSIONS=64
AZURE_OPENAI_MAX_COMPLETION_TOKENS=2048
```

Clients are constructed only when the factory selects `azure_openai`. Endpoints come from server settings only — never from request text or model output.

## Embedding index compatibility

`instruction_chunks.embedding` is fixed at **64** dimensions. Indexed content is tagged in singleton table `embedding_index_meta` (`provider`, `model` = deployment name, `dimension`).

- Mixing fake / ollama / azure_openai vectors in one corpus is rejected.
- Matching dimensions alone is not enough if provider or deployment differs.
- Automatic reindex is **not** performed.

## Manual reindex procedure (local)

`soteops-seed` **is** the supported reindex path: it rewrites `instruction_chunks` and updates `embedding_index_meta`. Preparation/retrieval refuse to mix a live embedder with a mismatched index.

1. Stop the API (optional but recommended).
2. Set the desired embedder env (fake, ollama, or azure_openai with enablement).
3. Run `uv run soteops-seed` so chunks and `embedding_index_meta` match that embedder.
4. Confirm `embedding_index_meta` shows the intended provider/deployment/dimension.

If seed was interrupted mid-way, clear and reseed:

```sql
TRUNCATE instruction_chunks RESTART IDENTITY CASCADE;
DELETE FROM embedding_index_meta;
```

then run `uv run soteops-seed` again. Automatic background reindex is not performed.

## Future opt-in smoke test (do **not** run without explicit authorization)

Paid Azure calls and live network use are **out of scope** until separately authorized in conversation.

When authorized later:

1. Fill real endpoint, key, and deployment names in a local `.env` (not committed).
2. Reindex instructions with the Azure embedding deployment (procedure above).
3. Run a single prepare against a synthetic request.
4. Record deployment names, region, and that results are not an evaluation claim.
5. Rotate/revoke the API key after the smoke test.

## Limitations

- Retries are application-level only (`LLM_MAX_RETRIES`); httpx has no extra retry transport.
- 401/403 fail immediately; 429/5xx/timeouts retry within the budget.
- Secrets, prompts, document bodies, and raw provider payloads are not logged by the adapter; exception text is redacted for key-like patterns.
- Approval hash binding and idempotent forwarding are unchanged and independent of this adapter.
