# Security and release review (MVP)

**Scope:** local demo prototype with synthetic data. Not a production security assessment.

Review date: 2026-09-16. Versions: policy `policy-v1`, auth demo-only, forwarding idempotency key `{request_id}:{payload_hash}`.

## Authentication and CSRF

| Control | Status | Evidence |
| --- | --- | --- |
| HttpOnly session cookie | Implemented | `backend/app/auth/sessions.py` |
| CSRF double-submit cookie + header | Implemented | `GET /auth/csrf`, `X-CSRF-Token` required on mutations — `test_csrf_is_required_for_mutations` |
| Demo auth gated by environment | Implemented | `DEMO_AUTH_ENABLED` only when `ENVIRONMENT` is `local`, `test`, `ci`, or `demo` |
| Passwords stored as Argon2 hashes | Implemented | Seeded identities only |
| No bearer tokens in localStorage | Enforced in frontend | Session cookie model documented in architecture |

## Authorization and ownership

| Control | Status | Evidence |
| --- | --- | --- |
| Requester cannot approve own request | Enforced | `test_self_approval_is_rejected` |
| Requester cannot access reviewer queue | Enforced | `test_requester_cannot_access_review_queue_or_approve` |
| Operator cannot approve | Enforced | `test_operator_cannot_approve` |
| Actor identity from session, not body | Implemented | API deps reject body-supplied actors |
| Invalid status transitions blocked | Enforced | `test_invalid_transition_rejected_request_cannot_be_approved` |
| Policy violations not approvable | Enforced | `test_policy_violation_cannot_be_approved` |

## Approval binding and stale proposals

| Control | Status | Evidence |
| --- | --- | --- |
| Approval binds to proposal id, revision, payload hash | Implemented | `Approval` model + migration partial unique index — `test_approval_partial_unique_index_matches_migration` |
| Edit invalidates prior approval | Enforced | `test_edit_invalidates_previous_proposal_and_stale_approval` |
| Stale proposal cannot forward | Enforced | `test_stale_proposal_cannot_submit` |
| Forward without approval blocked | Enforced | `test_forward_without_approval_is_blocked` |
| Concurrent approve attempts — one winner | Enforced | `test_concurrent_approval_attempts_reject_the_loser` |

## Forwarding, retries, and duplicates

| Control | Status | Evidence |
| --- | --- | --- |
| Idempotency key on submission | Implemented | `{request_id}:{payload_hash}` |
| Mock deduplicates by key | Implemented | `test_live_mock_idempotency_in_ci` |
| Concurrent dispatchers — single record | Enforced | `test_concurrent_dispatchers_do_not_duplicate` |
| Timeout → `unknown`, reconcilable | Enforced | `test_stale_in_flight_is_recovered_as_unknown` |
| Max retry attempts | Configurable | `FORWARD_MAX_ATTEMPTS` (default 3) |
| Destination URL not user-controlled | Implemented | Only `MOCK_INTEGRATION_URL` |

## Prompt injection and model boundaries

| Control | Status | Evidence |
| --- | --- | --- |
| Model cannot approve or skip rules | Enforced | `test_prompt_injection_cannot_approve_or_skip_rules` |
| Citation membership validation | Implemented | `validate_citation_membership` in workflow |
| Rules deterministic from policy file | Implemented | `seed/policy/v1.json` |

## Logging and secrets

| Control | Status | Notes |
| --- | --- | --- |
| JSON logs with correlation id | Implemented | Server-generated `X-Correlation-ID` |
| Raw credentials not logged | By design | Passwords never returned; forwarding logs omit payload secrets |
| Secrets not in git | Expected | `.env` local only; CI uses disposable `SESSION_SECRET` |
| Dependency audit in CI | Implemented | `pip-audit`, `npm audit` job |
| Secret scan in CI | Implemented | gitleaks on push/PR |

## CI release posture

- Workflow permissions: `contents: read` at workflow level; artifact upload jobs add minimal extra permissions.
- Actions pinned to full commit SHAs with version comments.
- No container publish or cloud deploy steps.
- Tests are not skipped or weakened for green builds.

## Dependency audit findings (accepted residual risk)

`pip-audit` (2026-09-16) reported advisories whose fix versions require **major** upgrades blocked by current pins (`langgraph>=0.6,<1`, `pytest>=8.4,<9` per `AGENTS.md`):

| Package | Advisory | Fix requires | Action |
| --- | --- | --- | --- |
| langgraph 0.6.11 | PYSEC-2026-83 | 1.0.10 | Deferred — major orchestrator bump |
| langgraph-checkpoint | PYSEC-2026-2573/2574 | 4.x | Deferred with langgraph |
| langgraph-sdk | PYSEC-2026-2194/2575 | 0.3.15 | Deferred with langgraph |
| pytest 8.4.2 | PYSEC-2026-1845 | 9.0.3 | Deferred — pytest 9 needs explicit upgrade task |

CI ignores these IDs with the rationale above. Do not ignore new advisories without documenting them here.

## Residual risks (documented, not silently fixed)

- Demo session secret in CI is not a production secret rotation story.
- CORS allows configured origins only; production hardening (HSTS, CSP) not in scope.
- Rate limiting and account lockout are not implemented (acceptable for local demo).
- Real Ollama path is optional and not evaluated in CI.
