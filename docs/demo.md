# Demo notes

This repository currently ships the foundation plus the access-request domain: local Postgres, health/readiness, a Finnish UI shell, synthetic identity seed, demo sessions, deterministic policy checks, and human approval APIs. LangGraph extraction, RAG, and mock forwarding are not in this slice.

Authentication is **local demo login**, not Entra ID. Sessions live in an HttpOnly cookie. Do not store bearer tokens in `localStorage`.

## What to show

1. Banner on `http://127.0.0.1:3000` stating synthetic data and no affiliation with Päijät-Hämeen hyvinvointialue.
2. Finnish copy describing the unvalidated working hypothesis.
3. `GET /health` returning `{"status":"ok"}` with `X-Correlation-ID`.
4. After migrations, `GET /ready` returning database and pgvector checks.
5. `uv run soteops-seed` inserting demo requester, reviewer, and operator identities (`@demo.invalid`).
6. `GET /auth/csrf` then `POST /auth/login` with a seeded demo password. Confirm `soteops_session` is HttpOnly and `/auth/me` reports `identity_provider: local-demo`.
7. Create a synthetic access request, inspect the deterministic proposal, then approve it from a reviewer session. An edit must invalidate the previous proposal hash.

Do not claim operational impact. Do not demo against real employees, patients, or IAM systems.
