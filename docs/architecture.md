# Architecture

SoteOps Agent is a modular FastAPI monolith plus a small mock integration service. PostgreSQL with pgvector is the only datastore. Access-request domain, deterministic policy, human approval, bounded LangGraph preparation, and reliable mock forwarding are implemented. The mock stores a request record; it does not create accounts.

```text
browser (Next.js, fi)
        -> FastAPI monolith (:8000)
                -> PostgreSQL + pgvector (:5432, localhost)
                -> mock-integration (:8001)
                -> optional local Ollama (manual)
                -> optional Azure OpenAI (opt-in; mocked tests; not CI)
```

## Runtime boundaries

- Docker Compose publishes ports on `127.0.0.1` only.
- `GET /health` is process liveness and does not touch the database.
- `GET /ready` checks PostgreSQL and the `vector` extension.
- Every HTTP response includes a **server-generated** `X-Correlation-ID`. Client-supplied IDs are ignored. Logs are JSON and include that id when present.
- Settings are validated with Pydantic. `DATABASE_URL` must be PostgreSQL. `LLM_PROVIDER` and `EMBEDDING_PROVIDER` are independently `fake`, `ollama`, or `azure_openai`. Selecting Azure requires `AZURE_OPENAI_ENABLED=true` and deployment settings; there is no fallback. Unknown settings fields are rejected.
- Seed data is synthetic and loaded only by `soteops-seed`.

## Authentication (local demo only)

Authentication is **local demo identity**, not Entra ID or any production directory. Seeded requester and reviewer accounts authenticate with passwords stored only as Argon2 hashes. The API issues a server-managed session in the HttpOnly `soteops_session` cookie and a readable `soteops_csrf` cookie. Mutations require `X-CSRF-Token`. Bearer tokens are not issued and must not be stored in `localStorage`.

`DEMO_AUTH_ENABLED` works only when `ENVIRONMENT` is `local`, `test`, `ci`, or `demo`, and `SESSION_SECRET` is at least 16 characters. Outside that explicit configuration, login and session-authenticated routes are rejected.

Actor, owner, and reviewer identities are taken from the session. Request bodies cannot set them. The model is not part of authentication or authorization.

## Domain and policy

`AccessRequest` holds the synthetic case. Each edit or resubmit creates a new `Proposal` and invalidates the previous proposal. `Approval` binds to that exact proposal id, revision, payload hash, and policy version. `Submission` is created on approve with `idempotency_key = "{request_id}:{payload_hash}"`. `AuditEvent` records allowlisted metadata only.

Deterministic rules live in versioned `seed/policy/v1.json`, not in an LLM response. The model may extract and explain. Rules decide whether a proposal is eligible for review.

## Preparation workflow

LangGraph runs only this bounded path and stops before approval and submission:

1. `extract_fields`
2. `validate_extracted_fields`
3. `retrieve_instructions`
4. `explain_findings`
5. `validate_citations`
6. `persist_proposal_or_clarification`

Progress is stored on `AccessRequest.status` and `preparation_runs`. A run left in `running` is marked `interrupted` on the next prepare. **Durable graph checkpoint resumption is not implemented.** Retries start from the current request text.

User text and retrieved documents are untrusted. Prompt injection cannot change authorization, tools, or policy rules. Citation IDs are checked for membership in the retrieval set; a valid ID does not prove that the passage supports the claim. Similarity scores and model self-confidence are not shown as calibrated probabilities.

## Forwarding

Approval and submission scheduling are one database transaction: a valid approve inserts `Submission` with `idempotency_key = "{request_id}:{payload_hash}"` and status `pending`. That row is the durable outbox. The dispatcher is a separate application service, not a LangGraph node.

Before the first send it re-checks the bound approval, current proposal revision, payload hash, and applicable policy version. The HTTP destination is only `MOCK_INTEGRATION_URL` (localhost / `mock-integration`). User text and model output cannot choose a URL. Raw payloads and credentials are not logged.

A timeout after send is `unknown`, not failure. The dispatcher looks up the idempotency key on the mock before deciding. Retries reuse the same key until `FORWARD_MAX_ATTEMPTS` (default 3). Edits and resubmits are blocked while a submission is `pending`, `in_flight`, or `unknown`, and while the request is `forwarding` or `forwarded`.

The mock exposes `POST /requests` with `Idempotency-Key`. The same key and payload return the same record. The same key with different content is `409`. Local-only `X-Mock-Fault` values: `success`, `fail-before`, `lost-response`, `unavailable`.

## Fake versus real inference

CI and the default local demo use deterministic **fake** LLM and embedding providers. Fake outputs are labelled `SYNTEETTINEN FAKE-TARJOAJA — ei mitattua mallisuorituskykyä` and must not be presented as measured model performance. Optional Ollama is local-only and must be enabled explicitly (`LLM_PROVIDER=ollama` and/or `EMBEDDING_PROVIDER=ollama` plus `OLLAMA_BASE_URL`).

Optional **Azure OpenAI** adapters (`LLM_PROVIDER=azure_openai` / `EMBEDDING_PROVIDER=azure_openai`) require `AZURE_OPENAI_ENABLED=true` and deployment settings. Maturity: **Implemented**, **tested with mocked Azure responses**, **not live-verified**. See [`docs/azure-openai.md`](azure-openai.md). Fake evaluation metrics are not Azure model quality. Managed identity is not implemented.

| Path | Inference |
| --- | --- |
| GitHub Actions (`LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`) | Fake LLM and hash embeddings only. No Ollama, no Azure, no paid/cloud models. |
| Default Compose / local demo | Same fake path unless env is changed. |
| `backend/tests/test_workflow.py` | Fake LLM unit tests. The Ollama timeout case is an httpx mock; it does not call a running model. |
| `backend/tests/test_azure_openai.py` | Azure adapters with **httpx MockTransport** only — no live Azure. |
| `backend/tests/test_retrieval.py` and request API tests | Full six-node graph against Postgres with fake providers. |
| `soteops-seed` | Embeddings from the configured embedding provider (fake in CI). Tracks `embedding_index_meta`. |
| Manual local Ollama | Real local `/api/chat` and/or `/api/embeddings` only when those providers are set to `ollama`. Not an evaluation harness. |
| Manual Azure OpenAI | Only when explicitly enabled; live smoke test requires separate human authorization. |

## Packages

| Path | Role |
| --- | --- |
| `backend/` | FastAPI app, SQLAlchemy, Alembic, seed command, LangGraph preparation |
| `mock-integration/` | Simulated receiver. Stores request records; does not create accounts |
| `frontend/` | Next.js App Router shell, Finnish copy, system fonts |
| `seed/` | Synthetic identities, policy, and Finnish instruction corpus |
| `.github/workflows/` | GitHub Actions CI |

Python dependencies are locked once at the repository root with uv (`uv.lock`). Frontend dependencies are locked with `frontend/package-lock.json` and installed using `npm ci`.
