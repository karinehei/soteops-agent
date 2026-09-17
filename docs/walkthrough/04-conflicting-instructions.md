# 4. Conflicting instructions

Show two contradictory **SYNTHETIC** instruction cards as evidence for a human. Retrieved text is not authorization. There is **no** demonstrated automatic conflict-detection status or conflict-based routing.

**Persona and start:** Requester `aino.esimerkki@demo.invalid` opens **Ristiriitaiset ohjeet** (`/requests/new?scenario=conflicting-instructions`: `EMP-4004`, `kirjaaja`, no end date).

![Clarification for missing end date, then Ristiriita A and Ristiriita B instruction cards shown in sequence](media/04-conflicting-instructions.gif)

[Static poster](media/04-conflicting-instructions-poster.png) — **Ristiriita A**.

## What the GIF shows

1. Status **Odottaa täsmennystä**. Overlay: clarification is the **missing end date**, not conflict routing. Extracted **Loppupäivä** is `—`.
2. **Ohjelähteet ja versiot** — **Ristiriita A: kirjaaja ilman loppupäivää (SYNTHETIC)** (`SYN-OHJE-RISTIRIITA-A-01-v1`): the excerpt says a registrar role *may* be recorded without an end date, in intended conflict with B. *Ohje on näyttöä tarkastajalle, ei valtuutus.*
3. Then **Ristiriita B: kirjaaja vaatii loppupäivän (SYNTHETIC)** (`SYN-OHJE-RISTIRIITA-B-01-v1`): the excerpt says a registrar role *always* requires an end date, in intended conflict with A. Same evidence disclaimer.

The GIF is an edited sequence of held frames so both cards are actually on screen, not only in the DOM. Overlay discloses `RETRIEVAL_TOP_K=8` for the **04 recapture stack only**.

## What this recording demonstrates

Retrieval can surface both instruction versions. Deterministic rules still require an end date, so the case stays in clarification. “Manual review” here means a person can read A and B; the case is **not** placed on the reviewer queue.

## Automated checks (not only the GIF)

- Playwright: [`frontend/e2e/demo-scenarios.spec.ts`](../../frontend/e2e/demo-scenarios.spec.ts) (`conflicting-instructions`) — **status only** (`Odottaa täsmennystä`)
- pytest: [`test_conflicting_current_instructions_are_both_retrieved`](../../backend/tests/test_retrieval.py) (`top_k=8`)
- Eval fixture: [`seed/evaluation/cases.json`](../../seed/evaluation/cases.json) `eval-025`

## Limitations

Default app `RETRIEVAL_TOP_K` is 4. This recapture used 8 because both conflict documents were absent at 4. That override is not a product default and did not apply to the 02/03 recaptures. There is no separate `conflict` request status.

## Implementation

- Fixture: [`frontend/src/lib/demo-scenarios.ts`](../../frontend/src/lib/demo-scenarios.ts) (`conflicting-instructions`)
- Corpus: [`seed/instructions.json`](../../seed/instructions.json) (`SYN-OHJE-RISTIRIITA-A-01-v1`, `SYN-OHJE-RISTIRIITA-B-01-v1`)
- Source cards: [`frontend/src/components/ProposalPanel.tsx`](../../frontend/src/components/ProposalPanel.tsx)
- Temporary end-date rule: [`backend/app/rules/engine.py`](../../backend/app/rules/engine.py)
- Recording notes: [media/provenance.md](media/provenance.md)

[Walkthrough overview](README.md) · Previous: [Prohibited access](03-prohibited-access.md) · Next: [Lost-response reconciliation](05-timeout-reconciliation.md)
