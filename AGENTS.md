# SoteOps Agent — agent constraints

Read this file before changing the repository. These constraints are accepted product and engineering decisions, not suggestions.

## What this project is

SoteOps Agent is an independent Finnish-language portfolio prototype. It prepares synthetic access requests for human review and, after approval, forwards a structured proposal to a mock downstream system.

The working hypothesis is that detecting missing information and conflicting requests before automation could reduce manual rework. Do not claim this benefit has been validated. Do not present the prototype as a production control, a real identity-management system, or an authorized public-sector solution.

## Affiliation

This work is inspired by publicly discussed public-sector workflow needs. It is not commissioned by, affiliated with, or connected to Päijät-Hämeen hyvinvointialue or any other real wellbeing services county. Do not use real organization names, employee identities, system identifiers, or policy text.

## Data and safety boundaries

- Use synthetic employees, organizations, systems, and policies only.
- Never introduce patient data, real employee data, real credentials, or real account provisioning.
- The LLM never grants access, never chooses the approver identity, and never overrides deterministic policy rules.
- Retrieved instructions are evidence for the reviewer, not authorization.
- The mock integration creates a request record, not an account.
- No cloud deployment, paid API calls, or external messages (email, SMS, Slack, real IAM) without explicit human authorization in the conversation.
- Do not modify AgentAudit, ICD-10 Assistant, or any other sibling project.

## Architecture

- Modular FastAPI monolith for the preparation, review, audit, and forwarding application.
- One small mock integration service that accepts approved proposals.
- PostgreSQL with pgvector is the only required datastore.
- LangGraph implements only the bounded preparation workflow. Do not add a general agent platform or a second orchestration framework.
- Do not add Redis, Kubernetes, message brokers, or extra queues.

## Stack

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL + pgvector, LangGraph
- Frontend: Next.js and TypeScript, Finnish UI copy
- Runtime: Docker Compose for local demo
- CI: GitHub Actions (not GitLab CI)
- Tests: pytest for backend and workflow; Playwright for the demo UI
- Models: deterministic fake providers in CI; optional local Ollama for real-model demonstrations

## Authorization and workflow rules

- Authentication is local demo identity with seeded synthetic users. The model is not part of authentication or authorization.
- Only an authenticated reviewer role may approve, reject, or request changes.
- A requester cannot approve any request, including their own.
- Reviewers approve an exact structured proposal snapshot (canonical content hash). Any edit invalidates prior approval and requires a new review.
- Downstream submission is allowed only after a still-valid human approval of the current proposal hash.
- Downstream calls are idempotent. Retries and ambiguous outcomes must not create duplicate mock request records.
- Failures stay visible and retryable; do not silently mark a request as forwarded.

## Implementation discipline

- Follow `docs/implementation-plan.md`. Keep this foundation slice free of cloud deployment, paid APIs, and real data.
- Preserve existing user changes. Do not drive-by refactor unrelated files.
- Keep secrets out of git. Local model endpoints and database URLs belong in env files that are not committed with credentials.
- Prefer deterministic rules and tests over prompt-only behavior wherever a decision is a control.
