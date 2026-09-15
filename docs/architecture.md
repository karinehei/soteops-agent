# Architecture

SoteOps Agent is a modular FastAPI monolith plus a small mock integration service. PostgreSQL with pgvector is the only datastore. This slice adds the access-request domain, deterministic policy checks, and a human approval boundary. LangGraph and RAG are still later work.

```text
browser (Next.js, fi)
        -> FastAPI monolith (:8000)
                -> PostgreSQL + pgvector (:5432, localhost)
                -> mock-integration (:8001)
```

## Runtime boundaries

- Docker Compose publishes ports on `127.0.0.1` only.
- `GET /health` is process liveness and does not touch the database.
- `GET /ready` checks PostgreSQL and the `vector` extension.
- Every HTTP response includes a **server-generated** `X-Correlation-ID`. Client-supplied IDs are ignored. Logs are JSON and include that id when present.
- Settings are validated with Pydantic. `DATABASE_URL` must be PostgreSQL. `LLM_PROVIDER` is `fake` or `ollama`. Unknown settings fields are rejected.
- Seed data is synthetic and loaded only by `soteops-seed`.

## Authentication (local demo only)

Authentication is **local demo identity**, not Entra ID or any production directory. Seeded requester and reviewer accounts authenticate with passwords stored only as Argon2 hashes. The API issues a server-managed session in the HttpOnly `soteops_session` cookie and a readable `soteops_csrf` cookie. Mutations require `X-CSRF-Token`. Bearer tokens are not issued and must not be stored in `localStorage`.

`DEMO_AUTH_ENABLED` works only when `ENVIRONMENT` is `local`, `test`, `ci`, or `demo`, and `SESSION_SECRET` is at least 16 characters. Outside that explicit configuration, login and session-authenticated routes are rejected.

Actor, owner, and reviewer identities are taken from the session. Request bodies cannot set them.

| Role | Access |
| --- | --- |
| requester | create, list, get, edit, and resubmit own requests; read own audit history |
| reviewer | authorized review queue; review, approve, or reject; cannot approve a request they own |
| operator | read requests and audit; cannot approve |

## Domain and policy

`AccessRequest` holds the synthetic case. Each edit or resubmit creates a new `Proposal` (extracted fields, excerpts, missing fields, rule violations, explanation, source references, downstream payload, policy version, payload hash) and invalidates the previous proposal. `Approval` binds to that exact proposal id, revision, payload hash, and policy version. `Submission` is created on approve with `idempotency_key = "{request_id}:{payload_hash}"`. `AuditEvent` records allowlisted metadata only.

Deterministic rules live in versioned `seed/policy/v1.json`, not in an LLM response: required fields, allowed job-role/access-role combinations, temporary access requires an end date, start date must not exceed end date, unknown systems or roles need clarification, and prohibited roles cannot be approved in the normal workflow.

## Packages

| Path | Role |
| --- | --- |
| `backend/` | FastAPI app, SQLAlchemy, Alembic, seed command |
| `mock-integration/` | Simulated receiver. Stores request records later; does not create accounts |
| `frontend/` | Next.js App Router shell, Finnish copy, system fonts |
| `seed/` | Synthetic identities JSON and versioned policy |
| `.github/workflows/` | GitHub Actions CI |

Python dependencies are locked once at the repository root with uv (`uv.lock`). Frontend dependencies are locked with `frontend/package-lock.json` and installed using `npm ci`.
