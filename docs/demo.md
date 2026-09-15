# Demo notes

This repository currently ships the **foundation**: local Postgres, health/readiness, a Finnish UI shell, and synthetic identity seed. The eight-step access-request workflow is not implemented yet.

## What to show

1. Banner on `http://127.0.0.1:3000` stating synthetic data and no affiliation with Päijät-Hämeen hyvinvointialue.
2. Finnish copy describing the unvalidated working hypothesis.
3. `GET /health` returning `{"status":"ok"}` with `X-Correlation-ID`.
4. After migrations, `GET /ready` returning database and pgvector checks.
5. `uv run soteops-seed` inserting demo requester, reviewer, and operator identities (`@demo.invalid`).

Do not claim operational impact. Do not demo against real employees, patients, or IAM systems.
