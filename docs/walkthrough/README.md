# SoteOps Agent walkthrough

SoteOps Agent is a **Finnish-language portfolio prototype**. It prepares synthetic access requests, applies deterministic policy rules, shows retrieved instructions as reviewer evidence, requires a human reviewer to approve an exact proposal snapshot, and then forwards that snapshot to a **mock** receiver.

The intended benefit is to help reviewers deal with incomplete requests and inspect supporting evidence **before** anything is sent downstream. That is a prototype hypothesis, not measured organizational impact. Do not treat these pages as a production control, a real identity-management system, or an authorized public-sector solution.

**You do not need to install anything to read this walkthrough.** The clips are in this repository. They were recorded from the local app with **simulated AI** (`LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`) and **synthetic** employees, systems, and policies. There is no hosted visitor workspace.

A short first pass: [01 Successful request](01-successful-request.md) → [03 Prohibited access](03-prohibited-access.md) → [06 Stale proposal](06-stale-proposal.md).

## Scenarios

| # | Purpose | Page |
| --- | --- | --- |
| 01 | Complete request, human approval, mock receipt (no account) | [Successful request](01-successful-request.md) |
| 02 | Missing end date corrected, then re-prepared for review (no approval) | [Missing end date](02-missing-end-date.md) |
| 03 | Prohibited role finding; the case is absent from the reviewer queue | [Prohibited access](03-prohibited-access.md) |
| 04 | Two conflicting instruction sources shown as evidence | [Conflicting instructions](04-conflicting-instructions.md) |
| 05 | Simulated lost response reconciled inside one forward | [Lost-response reconciliation](05-timeout-reconciliation.md) |
| 06 | Edit during review makes the open proposal stale | [Stale proposal](06-stale-proposal.md) |

All people, systems, and instruction titles in the clips are synthetic (`@demo.invalid`, `demo-hr-testi`, `SYNTHETIC`). Fake-provider labels are not measured model quality.

This is independent portfolio work. It is not affiliated with Päijät-Hämeen hyvinvointialue or any real wellbeing services county.

## How to read the GIFs

- Banner labels: **Requester** / **Reviewer**, plus `Local demo · Simulated AI · Synthetic data`. Extra overlay lines are documentation captions, not application UI.
- Scenarios **02, 03, and 04** are **edited sequences of held frames** taken from real local recordings (readable pauses). 01, 05, and 06 keep their original motion clips.
- Waiting periods are shortened. GIF duration is **not** application latency.
- `RETRIEVAL_TOP_K=8` was used for the **original full-stack capture** of 01, 05, and 06, and for the **04 recapture**. Recaptures of 02 and 03 used the default `TOP_K=4`. 8 is not the product default. The 04 GIF overlay names that recapture’s stack; it does not mean 04 is the only published clip recorded at 8.
- Capture-stage records describe the **video** stage (`gifs_generated=false` there). Conversion status is separate. Reader-facing facts: [media/provenance.md](media/provenance.md).

Media were generated and inspected locally. Documentation links were checked locally. GitHub rendering and the documentation GitHub Actions job have **not** been observed for this revision. Recruiter access is **not** confirmed.

To run the Finnish UI locally, see [setup](../setup.md). Capture operator notes: [recording.md](recording.md) and [recording-plan.md](recording-plan.md). Architecture: [architecture](../architecture.md).
