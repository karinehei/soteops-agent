# Evaluation methodology

**Not clinically or operationally validated.** Synthetic corpus for portfolio measurement only.

## Hypothesis under test

Detecting missing information, policy conflicts, and weak evidence **before** human review might reduce reviewer corrections and rework. This prototype measures technical signals on synthetic cases; it does **not** claim validated time savings.

## Dataset (`eval-v1`)

- Location: `seed/evaluation/cases.json` (35 labelled cases)
- Split: 20 `train`, 15 `held_out` (see `seed/evaluation/README.md`)
- Categories: complete, missing_fields, prohibited, ambiguous, evidence, prompt_injection, integration
- Held-out cases are **not** used for prompt tuning (`prep-v1` is fixed)

Regenerate (deterministic): `uv run python backend/scripts/generate_eval_cases.py`

## Versions recorded with each run

| Artifact | Version |
| --- | --- |
| Dataset | `eval-v1` |
| Policy | `policy-v1` |
| Prompt | `prep-v1` |
| Fake provider | `fake-prep-v1` |
| Real model (Ollama) | **Not run in CI** — optional local only |

## Metrics

| Metric | Definition |
| --- | --- |
| Field extraction accuracy | Share of expected extracted fields matching after validation |
| Missing-field precision | TP / (TP + FP) on missing-field keys |
| Missing-field recall | TP / (TP + FN) on missing-field keys |
| Retrieval recall@k | Share of cases where all required document IDs appear in top-k |
| Citation validity | Pipeline cases with no invented citation IDs |
| Routing accuracy | Status matches `ready_for_review` vs `needs_clarification` |
| Approvable accuracy | `is_approvable` matches expected boolean |
| Latency p50 / p95 | Wall time per case (fake provider, local Postgres) |

Control checks (separate pytest suites, not case JSON):

- **Approval boundary:** 10 scenarios (CSRF, roles, self-approval, stale hash, policy block, concurrent approve, forward gate)
- **Duplicate submission:** 3 scenarios (mock idempotency, concurrent dispatchers, timeout reconciliation)

## Running evaluation

```bash
# Requires Postgres (see docs/setup.md)
uv sync --locked --all-packages --group dev
cd backend && uv run alembic upgrade head && uv run soteops-seed && cd ..
uv run pytest backend/tests/test_evaluation.py -q
# Or CLI (held-out default):
uv run soteops-eval --split held_out --output docs/results/evaluation-report.json
```

Reports written by pytest: `docs/results/evaluation-held-out-fake.json` and `.md`.

## Fake vs real model results

| Environment | Provider | Report |
| --- | --- | --- |
| GitHub Actions / default local | `fake` | `docs/results/evaluation-held-out-fake.json` |
| Optional local Ollama | `ollama` | **Not automated** — run manually and save as `evaluation-held-out-ollama.json` if desired |
| Optional Azure OpenAI | `azure_openai` | **Not evaluated.** Adapter tests mock HTTP only. Fake-provider metrics are not Azure model quality. |

**Real model evaluation was not run for the committed report.** CI uses deterministic fake providers only. Azure OpenAI is **not live-verified**.

## Manual comparison protocol (time savings — not fabricated)

Use two reviewers and 6 synthetic requests (3 complete, 2 missing-field, 1 prohibited). Randomize order.

**Condition A — without assistant:** Reviewer reads raw text only, fills a paper checklist (fields, policy, evidence), records approve/reject/clarify and correction notes.

**Condition B — with assistant:** Same requests after preparation; reviewer sees extracted fields, rule findings, and citations.

Measure per request:

1. Time from open to decision (stopwatch)
2. Count of field corrections
3. Count of policy misses
4. Whether clarification was needed

Report median time and correction counts per condition. Do **not** extrapolate to operational savings without real workload sampling.

## Limitations

- Fake provider regex/structured outputs are not LLM generalization.
- Retrieval corpus is small and synthetic.
- Integration-failure cases are covered by forwarding pytest, not full UI E2E.
- No patient or real employee data.
