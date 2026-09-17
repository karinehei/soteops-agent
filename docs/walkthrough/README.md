# SoteOps Agent walkthrough

Recruiter-facing path through the **local** Finnish demo, as repository Markdown. Animated GIFs are recorded from the running application with synthetic data and fake model providers.

This is the portfolio presentation. It is **not** a public deployment, a production control, or an authorized wellbeing-services-county system. There is no visitor workspace on Vercel, Render, Neon, Azure, or GitHub Pages.

Raw Playwright videos stay in gitignored `artifacts/walkthrough/`. GIFs and posters are under [`media/`](media/README.md). Convert with `python scripts/walkthrough_gif.py` (FFmpeg). Waiting periods in the GIFs are shortened; GIF duration is not measured application latency.

| | |
| --- | --- |
| Local UI (developer stack) | `http://127.0.0.1:3000` after [`docs/setup.md`](../setup.md) |
| Recording commands | [`recording.md`](recording.md) |
| Recording plan | [`recording-plan.md`](recording-plan.md) |
| Spoken 3–5 min script | [`docs/demo-script.md`](../demo-script.md) |
| Architecture | [`docs/architecture.md`](../architecture.md) |

All employees, systems, and instructions in the clips are synthetic (`@demo.invalid`, `demo-hr-testi`, `SYNTHETIC` instruction titles). Default inference is `LLM_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake`. Fake findings are labelled and are not measured model quality.

Capture provenance: [`media/provenance.md`](media/provenance.md). Fake LLM and embeddings, isolated `soteops_walkthrough` database, installed Chrome. `RETRIEVAL_TOP_K=8` is not a product default; see that summary for per-scenario scope.

## Verified scenarios

| Scenario | Classification | Page | GIF |
| --- | --- | --- | --- |
| Successful request | Supported and recorded | [01](01-successful-request.md) | [media/01-successful-request.gif](media/01-successful-request.gif) |
| Missing end date | Supported and recorded | [02](02-missing-end-date.md) | [media/02-missing-end-date.gif](media/02-missing-end-date.gif) |
| Prohibited access | Supported and recorded | [03](03-prohibited-access.md) | [media/03-prohibited-access.gif](media/03-prohibited-access.gif) |
| Conflicting instructions | Recorded at `RETRIEVAL_TOP_K=8` (04 recapture stack); A and B in the GIF | [04](04-conflicting-instructions.md) | [media/04-conflicting-instructions.gif](media/04-conflicting-instructions.gif) |
| Timeout / lost response | Recorded in-dispatch reconcile; lingering `unknown` is test-only | [05](05-timeout-reconciliation.md) | [media/05-timeout-reconciliation.gif](media/05-timeout-reconciliation.gif) |
| Stale proposal after edit | Recorded during review; edit-after-approve is locked | [06](06-stale-proposal.md) | [media/06-stale-proposal.gif](media/06-stale-proposal.gif) |

What the table does **not** claim: validated time savings, real IAM provisioning, or live Azure/Ollama quality.

## Demo logins

| Role | Email |
| --- | --- |
| Requester | `aino.esimerkki@demo.invalid` |
| Reviewer | `ville.valvoja@demo.invalid` |
| Operator | `outi.operaattori@demo.invalid` |

Passwords are in `seed/identities.json`. A requester cannot approve. The model is not part of authentication.
