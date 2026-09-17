# Setup (WSL / Linux)

Local only. Do not deploy this prototype or point it at real identity systems. Recruiter-facing material is [`docs/walkthrough/`](walkthrough/README.md) recorded from this machine, not a public host.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.9+ (22 LTS recommended)
- Docker Engine with Compose v2
- Git

On WSL2, run the following from the repository root, for example `/mnt/d/soteops-agent`.

## Configure environment

```bash
cp .env.example .env
```

Replace every placeholder in `.env` with local synthetic values. Do not reuse production passwords or real directory credentials. Compose reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` from `.env`. The API reads `DATABASE_URL`.

`DEMO_AUTH_ENABLED` and `SESSION_SECRET` enable **local demo authentication only**. This is not Entra ID. Demo accounts are disabled unless `ENVIRONMENT` is `local`, `test`, `ci`, or `demo`. Do not put bearer tokens in `localStorage`; the browser should send the HttpOnly session cookie.

Example local-only values (not for any real system):

```bash
POSTGRES_USER=soteops
POSTGRES_PASSWORD=soteops
POSTGRES_DB=soteops
POSTGRES_HOST_PORT=5432
DATABASE_URL=postgresql+psycopg://soteops:soteops@127.0.0.1:5432/soteops
DEMO_AUTH_ENABLED=true
SESSION_SECRET=CHANGE_ME_LOCAL_SESSION_SECRET
```

## Start PostgreSQL with pgvector

If `docker compose up` cannot bind `5432`, set `POSTGRES_HOST_PORT` (and the same port in `DATABASE_URL`). Do not stop containers that belong to other projects.

WSL2 DNS sometimes fails to resolve PyPI or npm (`Resolving timed out`) even when IPv4 HTTPS works. In that case run `uv`/`npm` from Windows, or add IPv4 entries for `pypi.org`, `files.pythonhosted.org`, and `registry.npmjs.org` in WSL `/etc/hosts`.

```bash
docker compose up -d postgres
docker compose ps
```

## Python workspace

This repository uses **uv** as the only Python package manager. Install from the committed lockfile:

```bash
uv sync --locked --all-packages --group dev
```

Apply migrations and load synthetic identities plus SYNTHETIC instructions:

```bash
uv run --directory backend alembic upgrade head
uv run soteops-seed
```

Default `LLM_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake`. Those paths are what CI runs. To try local Ollama, set `LLM_PROVIDER=ollama` (and/or `EMBEDDING_PROVIDER=ollama`) and `OLLAMA_BASE_URL`; do not present that as a measured evaluation. Optional Azure OpenAI is documented in `docs/azure-openai.md`; keep it disabled unless live calls are separately authorized. This repository's tests mock Azure HTTP and do not call Azure.

Demo login uses the seeded `@demo.invalid` accounts and passwords in `seed/identities.json`. Those passwords are local demo credentials, not directory or Entra ID secrets.

Run the API and mock receiver:

```bash
uv run uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000
uv run uvicorn mock_integration.main:create_app --factory --app-dir mock-integration --host 127.0.0.1 --port 8001
```

Health and readiness:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/ready
```

## Frontend

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The UI uses system fonts and must not fetch Google Fonts.

## Checks

```bash
uv lock --check
uv run ruff format --check backend mock-integration
uv run ruff check backend mock-integration
uv run mypy backend/app mock-integration/mock_integration
uv run pytest --junitxml=junit.xml --cov --cov-report=term-missing
cd frontend && npm ci && npm run lint && npm run typecheck && npm run build
```

Integration tests require Postgres on `127.0.0.1:5432` after migrations. CI sets `LLM_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake` and does not call Ollama, Azure, or other cloud AI. The Ollama adapter is covered by mocked timeout tests only. Azure OpenAI tests use httpx MockTransport only. If port `5432` is already used by another project, set `POSTGRES_HOST_PORT` and `DATABASE_URL` to a free local port instead of stopping that project.

GitHub Actions starts the mock integration on `127.0.0.1:8001` before pytest. Forwarding tests also drive the mock in-process. `FORWARD_MAX_ATTEMPTS` defaults to 3; a timeout after send is reconciled by idempotency-key lookup and does not mint a new key.

## Optional Compose stack

After `.env` is filled:

```bash
docker compose up --build
```

API `http://127.0.0.1:8000`, mock integration `http://127.0.0.1:8001`, web `http://127.0.0.1:3000`.
