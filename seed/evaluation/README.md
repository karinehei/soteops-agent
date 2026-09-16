# Synthetic evaluation dataset (eval-v1)

**Not real patient, employee, or policy data.** For portfolio measurement only.

## Split policy

| Split | Purpose | Count |
| --- | --- | --- |
| `train` | Documented examples; **not used for prompt tuning** in this repository (prompt is fixed `prep-v1`) | 20 |
| `held_out` | CI gate — regression on unseen case IDs only | 15 |

Do not move held-out cases into prompts, few-shot examples, or fake-provider regex tuning without relabelling the split.

## Case schema

Each entry in `cases.json`:

- `id` — stable identifier (`eval-NNN`)
- `split` — `train` | `held_out`
- `category` — `complete` | `missing_fields` | `prohibited` | `ambiguous` | `evidence` | `prompt_injection` | `integration`
- `input.original_text` — synthetic free text
- `input.form_fields` — optional structured hints (may be empty)
- `retrieval.query` — query passed to retrieval ranker
- `retrieval.target_system` — filter for `applies_to_systems`
- `retrieval.as_of` — ISO date for validity filter
- `expected.extracted_fields` — fields expected after validation (subset checked)
- `expected.missing_fields` — required missing keys
- `expected.violation_codes` — deterministic rule codes
- `expected.status` — `ready_for_review` | `needs_clarification`
- `expected.approvable` — boolean
- `expected.retrieval_document_ids` — documents that must appear in top-k (empty = none required)
- `expected.retrieval_must_exclude` — documents that must not appear (e.g. expired)
- `notes` — human-readable intent

## Versions recorded with each run

- Dataset: `eval-v1` (`cases.json`)
- Policy: `policy-v1` (`seed/policy/v1.json`)
- Prompt: `prep-v1`
- Fake model: `fake-prep-v1`
- Real model: **not evaluated in CI** (optional local Ollama only)
