# 3. Prohibited access

Show a deterministic policy block for `tuotanto-superadmin`. The model does not grant access. The case stays out of the reviewer queue.

**Persona and start:** Requester `aino.esimerkki@demo.invalid` opens **Kielletty käyttöoikeus** (`/requests/new?scenario=prohibited-role`: `EMP-3003`, `tuotanto-superadmin`). Reviewer `ville.valvoja@demo.invalid` then opens **Tarkastusjono**.

![Requester view of Kielletty käyttöoikeus for EMP-3003 tuotanto-superadmin, then an empty reviewer queue](media/03-prohibited-access.gif)

[Static poster](media/03-prohibited-access-poster.png) — full **Kielletty käyttöoikeus** finding.

## What the GIF shows

1. Request identity: **EMP-3003**, requested role **tuotanto-superadmin**, status **Odottaa täsmennystä**. No approve control on the requester page.
2. Findings: **Kielletty käyttöoikeus:** *This access role cannot be approved in the normal workflow.*
3. Reviewer **Tarkastusjono** is **Jono tyhjä** (*Ei tarkastusta odottavia pyyntöjä.*). The overlay names EMP-3003 so the empty queue is this request’s exclusion, not a random idle screen.

The GIF is an edited sequence of held frames from the local recapture (isolated database, so no other ready cases were listed).

## What this recording demonstrates

Policy, not the model, blocks the prohibited role. Queue listing is only `ready_for_review` / `in_review`, so this `needs_clarification` case does not appear for review.

## Automated checks (not in the GIF)

- Playwright: [`frontend/e2e/demo-scenarios.spec.ts`](../../frontend/e2e/demo-scenarios.spec.ts) (`prohibited-role`) — **Odottaa täsmennystä**, no requester eligibility card
- pytest: [`test_prohibited_role_cannot_be_approved`](../../backend/tests/test_rules.py) — rule engine, `is_approvable` is false
- Recording capture called `POST /requests/{id}/approve` and received **409** `Request is not awaiting review` because the status never entered review. That API detail is **not** on screen.
- [`test_policy_violation_cannot_be_approved`](../../backend/tests/test_access_requests.py) also posts approve while the case is still `needs_clarification`, so it hits the same “not awaiting review” gate.

The later API guard *Policy violations must be resolved before approval* (approve while the request **is** in a reviewable status but still has violations) was **not** exercised by that 409.

## Limitations

No fabricated UI error. Direct-URL reviewer page with a disabled **Hyväksy tarkka ehdotus** is implemented but **not** in this GIF. Recapture used default `RETRIEVAL_TOP_K=4`. Overlay text on the queue is a documentation caption.

## Implementation

- Fixture: [`frontend/src/lib/demo-scenarios.ts`](../../frontend/src/lib/demo-scenarios.ts) (`prohibited-role`)
- Rule + English message: [`backend/app/rules/engine.py`](../../backend/app/rules/engine.py)
- Policy list: [`seed/policy/v1.json`](../../seed/policy/v1.json) (`prohibited_access_roles`)
- Queue filter: [`backend/app/api/requests.py`](../../backend/app/api/requests.py) (`review_queue`)
- Approve 409 order: [`backend/app/services/approvals.py`](../../backend/app/services/approvals.py)
- Empty queue UI: [`frontend/src/app/review/page.tsx`](../../frontend/src/app/review/page.tsx)

[Walkthrough overview](README.md) · Previous: [Missing end date](02-missing-end-date.md) · Next: [Conflicting instructions](04-conflicting-instructions.md)
