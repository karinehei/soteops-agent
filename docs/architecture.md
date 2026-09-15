# Architecture (foundation)

SoteOps Agent is a modular FastAPI monolith plus a small mock integration service. PostgreSQL with pgvector is the only datastore. LangGraph, review APIs, and RAG are planned next; they are not in this foundation slice.

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

## Packages

| Path | Role |
| --- | --- |
| `backend/` | FastAPI app, SQLAlchemy, Alembic, seed command |
| `mock-integration/` | Simulated receiver. Stores request records later; does not create accounts |
| `frontend/` | Next.js App Router shell, Finnish copy, system fonts |
| `seed/` | Synthetic identities JSON |
| `.github/workflows/` | GitHub Actions CI |

Python dependencies are locked once at the repository root with uv (`uv.lock`). Frontend dependencies are locked with `frontend/package-lock.json` and installed using `npm ci`.
