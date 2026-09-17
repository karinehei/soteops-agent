# 2. Missing end date

Show that a temporary `kirjaaja` request without an end date is held for clarification, then that filling the date and saving re-prepares the case into **Odottaa tarkastusta**. **No approval occurs in this clip.**

**Persona and start:** Requester `aino.esimerkki@demo.invalid` opens **Määräaikainen ilman loppupäivää** (`/requests/new?scenario=temporary-missing-end`: `EMP-2002`, `kirjaaja`, no `end_date`).

![Requester clarifies a missing end date, fills 2026-12-31, then status Odottaa tarkastusta with no missing fields](media/02-missing-end-date.gif)

[Static poster](media/02-missing-end-date-poster.png) — status after re-preparation.

## What the GIF shows

1. After submit, status is **Odottaa täsmennystä**. **Loppupäivä** is empty (`—`).
2. **Muokkaa ja täsmennä**: the requester fills **Loppupäivä** `31/12/2026` and saves (**Lähetetään…**).
3. After re-preparation the badge is **Odottaa tarkastusta** and extracted **Loppupäivä** is `2026-12-31`.
4. Findings show **Ei puuttuvia kenttiä eikä estäviä sääntöhavaintoja.** There is no approve button on the requester page.

The GIF is an edited sequence of held frames from the local recapture.

## What this recording demonstrates

Deterministic rules send the incomplete temporary request to clarification. After the date is supplied, preparation runs again and the case becomes eligible for review. The clip stops there.

**Known UI issue:** after the save, the app shows *Pyyntöä muokattiin. Edellinen hyväksyntä ei ole enää voimassa — tarvitaan uusi tarkastus.* This scenario had **no** prior approval. That sentence is current copy for any invalidated proposal, not proof that an approval happened.

## Automated checks (not only the GIF)

- Playwright: [`frontend/e2e/clarification-correction.spec.ts`](../../frontend/e2e/clarification-correction.spec.ts) — fill end date, then **Odottaa tarkastusta** and empty findings
- Playwright: [`frontend/e2e/demo-scenarios.spec.ts`](../../frontend/e2e/demo-scenarios.spec.ts) (`temporary-missing-end`) — initial **Odottaa täsmennystä**, no eligibility card for the requester
- pytest: [`test_temporary_access_requires_end_date`](../../backend/tests/test_rules.py)
- pytest: [`test_resubmit_creates_new_revision`](../../backend/tests/test_access_requests.py) — no-edit resubmit path (not the GIF)

## Limitations

No reviewer appears. Recapture used default `RETRIEVAL_TOP_K=4` (this case does not depend on retrieval top-k). Overlay “no approval in this clip” is a documentation caption.

## Implementation

- Fixture: [`frontend/src/lib/demo-scenarios.ts`](../../frontend/src/lib/demo-scenarios.ts) (`temporary-missing-end`)
- Rules: [`backend/app/rules/engine.py`](../../backend/app/rules/engine.py), [`seed/policy/v1.json`](../../seed/policy/v1.json) (`temporary_access_roles`)
- Invalidation copy: [`frontend/src/components/RequestDetailView.tsx`](../../frontend/src/components/RequestDetailView.tsx)
- Empty findings copy: [`frontend/src/components/ProposalPanel.tsx`](../../frontend/src/components/ProposalPanel.tsx)

[Walkthrough overview](README.md) · Previous: [Successful request](01-successful-request.md) · Next: [Prohibited access](03-prohibited-access.md)
