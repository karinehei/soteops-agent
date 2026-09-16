# Portfolio demo script (3–5 minutes)

**Synthetic data only. Not affiliated with any real wellbeing services county. Not production-ready.**

Prerequisites: `docker compose up --build` or local API + frontend (see README). Fake AI providers (default).

Demo users (passwords in `seed/identities.json`):

- Requester: `aino.esimerkki@demo.invalid`
- Reviewer: `ville.valvoja@demo.invalid`
- Operator: `outi.operaattori@demo.invalid`

## 0:00 — Context (30 s)

Open `http://127.0.0.1:3000`. Point to the banner: independent prototype, synthetic employees, unvalidated hypothesis about catching missing info before review.

## 0:30 — Successful workflow (90 s)

1. **Login** as requester (`/login`).
2. **New request** (`/requests/new`) — use demo scenario “Täydellinen pyyntö” or paste:

   > Pyydän lukuoikeutta demo-hr-testi -järjestelmään synteettiselle työntekijälle EMP-1001. Rooli sairaanhoitaja, työsuhde vakituinen, yksikkö demo-osasto, alkaen 2026-10-01.

3. Show **proposal**: extracted fields, deterministic policy OK, SYNTHETIC citations, fake-provider label.
4. **Logout → login as reviewer** (`/review`).
5. **Approve** exact proposal snapshot.
6. **Operator or reviewer**: trigger forward / show submission panel — mock record id, idempotency (repeat forward → same id).

Say explicitly: mock stores a request record; **no account is created**.

## 2:00 — Clarification case (60 s)

1. Login as requester. Choose demo scenario “Puuttuva kenttä” or submit text **without** employee id / end date for määräaikainen role.
2. Show status **Tarkennusta tarvitaan** / `needs_clarification`, missing-field list, rule findings.
3. Explain: system routes to clarification, not silent approval.

## 3:00 — Timeout reconciliation (60 s)

1. Login as reviewer with a **ready** approved request (from happy path or pre-seeded).
2. Open submission / forward UI. If local demo supports fault injection (`X-Mock-Fault: lost-response` via API or demo control), trigger forward.
3. Show status **Tuntematon / unknown** — not marked as success.
4. **Retry forward** — dispatcher reconciles via idempotency key on mock; same record id returned.

Alternative if UI fault control unavailable: run `uv run pytest backend/tests/test_forwarding.py::test_stale_in_flight_is_recovered_as_unknown -q` and narrate the UI states from docs.

## 4:00 — Close (30 s)

- Human approval required; model does not grant access.
- Evaluation on 35 synthetic cases (fake provider in CI).
- Limitations: not validated, not production IAM.

## Feature honesty table (spoken summary)

| Area | Status |
| --- | --- |
| Preparation + review UI | Implemented |
| Mock forwarding + idempotency | Implemented |
| Real Entra / IAM | Future / out of scope |
| Measured time savings | Unverified — manual protocol only |
| Real LLM evaluation | Not run in CI |
