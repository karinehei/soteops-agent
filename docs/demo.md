# Demo notes

This repository currently ships foundation, access-request domain, human approval, bounded LangGraph preparation, and forwarding of an approved proposal to the local mock integration. The mock stores a request record and does not grant access.

Authentication is **local demo login**, not Entra ID. Sessions live in an HttpOnly cookie. Do not store bearer tokens in `localStorage`.

CI and the default local demo use **fake** LLM and embedding providers. Fake findings are labelled and must not be presented as measured model performance. Optional Ollama is a manually enabled local adapter (`LLM_PROVIDER=ollama` and/or `EMBEDDING_PROVIDER=ollama` plus `OLLAMA_BASE_URL`). It is not used in GitHub Actions. See `docs/architecture.md` for which tests use fake versus real inference.

## What to show

1. Banner on `http://127.0.0.1:3000` stating synthetic data and no affiliation with Päijät-Hämeen hyvinvointialue.
2. Finnish copy describing the unvalidated working hypothesis.
3. `GET /health` returning `{"status":"ok"}` with `X-Correlation-ID`.
4. After migrations, `GET /ready` returning database and pgvector checks.
5. `uv run soteops-seed` inserting demo identities and SYNTHETIC Finnish instructions.
6. `GET /auth/csrf` then `POST /auth/login` with a seeded demo password.
7. Create a synthetic access request. The proposal shows extracted fields with input excerpts, deterministic rule findings, retrieved SYNTHETIC citations, and a fake-provider label. Human review is still required. An edit invalidates the previous proposal hash.
8. A reviewer approves the exact proposal hash. `POST /requests/{id}/forward` sends the frozen payload to the mock with a stable idempotency key. Repeat forwards return the same mock record id. The mock does not create an account.

Do not claim operational impact. Do not demo against real employees, patients, or IAM systems.
