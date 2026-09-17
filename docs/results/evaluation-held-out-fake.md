# Evaluation report (fake provider, held-out split)

**Not clinically validated. Synthetic demo only.**

- Dataset: `eval-v1`
- Policy: `policy-v1`
- Prompt: `prep-v1`
- Provider: `fake` (real model run: **False**)
- Cases: **15/15 passed**

## Metrics

| Metric | Value |
| --- | --- |
| Field extraction accuracy | 1.000 |
| Missing-field precision | 1.000 |
| Missing-field recall | 1.000 |
| Retrieval recall@k | 1.000 |
| Citation validity | 1.000 |
| Routing accuracy | 1.000 |
| Approvable accuracy | 1.000 |
| Latency p50 (ms) | 42.47151799791027 |
| Latency p95 (ms) | 49.664472997392295 |

## Control checks (pytest suites)

- Approval boundary: 10/10 scenarios covered
- Duplicate submission: 3/3 scenarios covered

## Limitations

- Synthetic demo corpus only — not clinically or operationally validated.
- CI uses fake LLM/embedding providers; results are not measured model performance.
- No real Ollama/cloud model was run for this report unless explicitly noted.
- Time-savings hypothesis is not quantified; see manual comparison protocol in docs/evaluation.md.
- Integration-failure controls are covered by dedicated pytest forwarding tests.
