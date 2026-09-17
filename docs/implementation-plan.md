# SoteOps Agent — implementation plan

Status: foundation through portfolio evaluation, security scanning CI, and demo documentation are implemented (sections 1–8 and 12). Recruiter presentation is a GitHub Markdown walkthrough (`docs/walkthrough/`); GIFs are planned, not yet recorded (section 13). Do not claim the product hypothesis has been validated.

## 1. Product

SoteOps Agent is a Finnish-language portfolio prototype. A requester submits a synthetic free-text access request. The application extracts a structured proposal, runs deterministic checks, retrieves versioned synthetic instructions, and drafts a Finnish explanation plus clarification questions. An authorized human reviews the exact proposal. Only after a still-valid approval does the application forward that proposal to a mock integration, which stores a request record.

Working hypothesis, not a validated result: catching missing fields and conflicting requests before automation could reduce later manual rework. Demos and copy must not claim operational impact.

This is an independent prototype. It is not commissioned by, affiliated with, or connected to Päijät-Hämeen hyvinvointialue.

## 2. MVP

The first deliverable is a local Docker Compose demo that completes this path with synthetic data:

1. Requester submits Finnish free-text.
2. Bounded LangGraph workflow extracts structured fields and keeps supporting excerpts.
3. Deterministic rules flag missing fields and prohibited combinations.
4. RAG retrieves applicable versioned synthetic instructions from pgvector.
5. The model writes a Finnish finding explanation and a clarification draft. It does not decide the outcome.
6. A reviewer inspects the exact structured proposal, evidence, and rule findings, then approves, rejects, or requests changes.
7. On valid approval, the monolith forwards the frozen proposal to the mock integration.
8. Failed or ambiguous forwards are retryable with the same idempotency key and never create a second mock record.

MVP also includes:

- Seeded synthetic users, organizations, systems, and instruction corpus
- Local session authentication and role checks
- Append-only audit events for submit, extract, rule findings, retrieval, review, invalidation, forward, and retry
- Fake LLM/embedding providers for CI; optional Ollama profile for a live local demo
- pytest coverage of rules, state transitions, invalidation, and idempotency
- Playwright coverage of the Finnish happy path plus one failure/retry path

## 3. Explicit non-goals

- Real employee, patient, or organization data
- Real account provisioning, AD/Entra/IAM integration, or mailbox/SMS notifications
- Cloud deployment, paid model APIs, or any external network call without explicit authorization
- Public visitor hosting (Vercel, Render, Neon, Azure app hosting, GitHub Pages, shared demo workspaces). Recruiter presentation is repository Markdown plus GIFs from the local app.
- LLM-granted access, LLM-selected approver, or LLM override of rules
- Treating retrieved instructions as authorization
- Redis, Kubernetes, a general agent platform, or a second orchestrator besides LangGraph
- GitLab CI
- Changes to AgentAudit, ICD-10 Assistant, or other sibling repositories
- Claims that the hypothesis is proven

## 4. Directory structure

Modular monolith plus one mock service:

```text
soteops-agent/
  AGENTS.md
  docs/
    implementation-plan.md
    architecture.md
    setup.md
    demo.md
  compose.yaml                  # api, web, postgres, mock-integration
  .github/workflows/ci.yml
  backend/                      # FastAPI application
    pyproject.toml
    alembic/
    app/
      main.py
      core/                     # config, db session, logging
      models/                   # SQLAlchemy identity entities
      api/                      # HTTP routers
    tests/
  mock-integration/             # small FastAPI mock receiver
    mock_integration/
    tests/
  frontend/                     # Next.js App Router, TypeScript
    src/
  seed/                         # synthetic users, requests, instruction markdown
```

No extra packages, workers, or shared libraries until a concrete need appears.

## 5. Entities

| Entity | Responsibility |
| --- | --- |
| `User` | Seeded synthetic identity with role `requester`, `reviewer`, or `operator`. |
| `Organization` | Synthetic org used in requests and instructions. |
| `AccessTarget` | Synthetic system the request is about. |
| `InstructionDocument` | Versioned Finnish (or bilingual) synthetic policy text, embedding, `version`, `is_current`. |
| `AccessRequest` | Case record: raw text, requester, status, pointer to current proposal. |
| `Proposal` | Immutable structured snapshot: fields, excerpts, rule findings, retrieval citations, Finnish explanation, clarification draft, canonical `content_hash`. |
| `ReviewDecision` | Human approve / reject / request_changes against one proposal id + hash, with reviewer id and comment. |
| `DownstreamSubmission` | Forward attempt: `idempotency_key`, status, mock record id, error, attempt count. |
| `AuditEvent` | Append-only actor, action, entity, payload. No secrets. |

Extracted proposal fields (MVP): subject (synthetic employee ref), organization, access target, requested role/level, environment (`test`/`prod`), time bound (`starts_at`, `ends_at`), justification, privileged flag, shared-account flag. Unknown values stay `null` with excerpts when present. The model may not invent identifiers that are not in the source text or seed catalog.

## 6. State transitions

`AccessRequest.status` is the case state. Proposal rows are immutable; a new edit creates a new proposal and points the request at it.

```text
submitted
  → preparing
      → needs_clarification     # blocking missing fields and/or prohibited combinations
      → ready_for_review        # non-blocking findings allowed
          → in_review
              → approved        # valid ReviewDecision on current hash
              → rejected
              → needs_clarification
  approved → forwarding → forwarded
  approved → forwarding → forward_failed → forwarding (retry) → forwarded
```

Invalidation (any status except `rejected` / `forwarded`):

- Requester edits raw text or an operator rebuilds extraction → new `Proposal` → status `preparing`, then `needs_clarification` or `ready_for_review`.
- Existing `ReviewDecision` rows remain in history but are not valid for forwarding.
- `approved` or `in_review` becomes `preparing` immediately after the edit.

Terminal-ish states:

- `rejected`: no forward. A later edit reopens as `preparing`.
- `forwarded`: mock accepted the current hash. Further edits create a new request or a new proposal that cannot reuse the old submission key.
- `forward_failed`: still approved if the hash is unchanged; retry allowed.

LangGraph owns only `preparing` (the six nodes in section 10) and stops before approval and submission. Human review and forwarding are application services that resume from persisted request state. Durable graph checkpoint resumption is not implemented.

## 7. Authentication and authorization

- Local demo login against seeded users. Session cookie or signed server session; no external IdP in MVP.
- The LLM stack is unreachable from auth dependencies.
- Role gates:
  - `requester`: create and edit own requests; read own case; cannot hit review or forward endpoints.
  - `reviewer`: read any case; approve, reject, or request changes; cannot edit requester text.
  - `operator`: read audit, retry `forward_failed` for a still-valid approval; cannot approve unless the user also has `reviewer`.
- Approver identity is the authenticated reviewer, never a model output or a field extracted from the request.
- `/review` and `/forward` verify role, current proposal id, and `content_hash` on the server.
- Retrieved instructions appear as citations. They do not grant the reviewer extra rights and do not bypass rules.

## 8. Approval invalidation after edits

1. Persist each proposal as canonical JSON (sorted keys, no volatile timestamps) and store `sha256(content_hash)`.
2. `ReviewDecision` stores `proposal_id` and the hash that was shown.
3. Approve is accepted only when `decision.hash == current_proposal.content_hash` and request status is `in_review` or `ready_for_review`.
4. Any change to raw text or a workflow rebuild inserts a new proposal, updates `AccessRequest.current_proposal_id`, writes `proposal_invalidated`, and clears forward eligibility.
5. The UI must re-fetch the proposal before acting. A stale approve payload returns `409` with the new hash.
6. Forwarding re-checks the same predicate so a race between edit and approve cannot ship an old snapshot.

## 9. Idempotent downstream submission

- Create `DownstreamSubmission` when an approval becomes valid, before the HTTP call, with `idempotency_key = "{request_id}:{content_hash}"`.
- Unique constraint on `idempotency_key` in both the monolith and mock-iam.
- Mock `POST /requests` is create-or-return: same key and payload returns the existing record id and payload hash. Same key with different content is rejected.
- Retry on timeout, 5xx, or ambiguous “unknown outcome” uses the same key. Do not mint a new key for retries. Timeouts are reconciled with `GET /requests?idempotency_key=`.
- Mark `forwarded` only after the mock returns a record id for that key and payload hash, or lookup confirms the record. Otherwise `forward_failed` or `unknown`.
- If the current proposal hash differs from the submission key, do not retry; require a new approval and a new key.
- Mock-iam stores a request record only. It does not create accounts, credentials, or group memberships.
- Edits are blocked while submission is pending, in flight, or unknown, and while the request is forwarding or forwarded.

## 10. Workflow and providers

LangGraph nodes, in order:

1. `extract_fields`
2. `validate_extracted_fields`
3. `retrieve_instructions`
4. `explain_findings`
5. `validate_citations`
6. `persist_proposal_or_clarification`

The graph stops after persist. It has no tools that approve, reject, or call mock-iam. `preparation_runs` records the current node and marks leftover `running` rows as `interrupted`. Durable graph checkpoint resumption is not implemented; a retry starts from the current request text.

- AI may extract and explain. Deterministic `validate_extracted_fields` plus policy rules decide review eligibility. Unknown or ambiguous values stay unknown. Values that are not in the source text are dropped. Supporting input excerpts are stored beside extracted values.
- Retrieval combines lexical overlap and vector rank, filters by validity dates and target system, deduplicates by `document_id`, uses stable `source_id` values, and respects `RETRIEVAL_TOP_K`. Missing evidence yields no supported answer.
- Citation IDs are membership-checked. A valid ID does not prove that the passage supports the claim. Similarity and model self-confidence are not shown as calibrated probabilities.
- `providers/fake.py` is the CI and default path. Fake outputs are labelled and are not measured LLM performance.
- `providers/ollama.py` is opt-in (`LLM_PROVIDER` and `EMBEDDING_PROVIDER` are independent). It is not used in GitHub Actions.
- `providers/azure_openai.py` is opt-in (`AZURE_OPENAI_ENABLED` plus provider selection, local API key). Tests mock HTTP only. Not live-verified. Not used in GitHub Actions or default Compose. See `docs/azure-openai.md`.

## 11. Tests and measurable demo outcomes

**pytest (CI, fake providers)**

- Rules: missing fields and each prohibited combination
- State machine: legal transitions only
- Invalidation: edit after approve → `409` on old hash; forward refused
- Idempotency: two forwards / timeout-then-retry → one mock record
- Authz: requester cannot approve; anonymous cannot review
- RAG: retrieval returns versioned citations; missing corpus is a finding, not a grant

**Playwright**

- Finnish requester submit → reviewer sees fields, excerpts, findings, citations, clarification draft → approve → mock record id visible
- Retry after simulated mock failure still shows a single downstream record
- Stale approve after edit is rejected in the UI

**Demo measurements (instrument, do not market as proof)**

| Signal | MVP target |
| --- | --- |
| Seeded requests with at least one missing-field finding | visible count in UI/audit |
| Seeded requests with a prohibited combination | visible count; none reach `forwarded` without resolution + new approval |
| Duplicate mock records for one idempotency key | 0 |
| Successful forward without matching valid `ReviewDecision` | 0 |
| Successful approve of a non-current hash | 0 |
| Human reviewer id recorded on every `forwarded` case | 100% |

## 12. Implementation order (after this plan is accepted)

1. Compose, Postgres/pgvector, Alembic models, seed identities **(done in foundation)**
2. Auth, request CRUD, audit **(done in this slice)**
3. Rules engine and proposal hashing **(done in this slice)**
4. Fake providers, LangGraph preparation graph, RAG ingest/retrieve **(done in this slice)**
5. Review API + invalidation **(done in this slice)**
6. mock-integration + idempotent forward/retry **(done in this slice)**
7. Finnish Next.js UI for the eight-step path **(done in this slice)**
8. Remaining pytest + Playwright coverage for the full demo path **(done — Playwright E2E in CI)**
9. Synthetic evaluation corpus (35 cases, held-out split) + metrics harness **(done — `seed/evaluation/`, `test_evaluation.py`)**
10. Security/release checks (pip-audit, npm audit, gitleaks, `docs/security-review.md`) **(done)**
11. Portfolio docs (README, `docs/evaluation.md`, `docs/demo-script.md`, results under `docs/results/`) **(done)**
12. Recruiter walkthrough pages and recording plan under `docs/walkthrough/` **(done — GIFs not recorded)**

Stop here for review.

## 13. Portfolio presentation (walkthrough, not public deploy)

Historical local architecture is unchanged: Compose publishes `127.0.0.1` only; CI uses fake providers; optional Ollama/Azure remain opt-in and are not the recruiter path.

**Decision:** present the prototype on GitHub as Markdown under [`docs/walkthrough/`](walkthrough/README.md), with animated GIFs recorded from the actual local UI. This **replaces** a planned public deployment. Do not add Vercel, Render, Neon, Azure hosting, GitHub Pages, or a public visitor workspace for this presentation.

Recording constraints (also in `docs/walkthrough/recording-plan.md`):

- Synthetic identities and `policy-v1` only
- `LLM_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake`; no live Azure or Ollama during capture
- Do not fabricate screens. Classify each scenario as recordable, test-only, unimplemented, or blocked
- Edit after approve is locked by the pending submission; invalidation GIFs use the stale-proposal path during review
- Lingering downstream `unknown` is recovered in tests; the labelled `lost-response` UI control reconciles in the same forward call

GIFs are not in the tree until a recording pass follows that plan.
