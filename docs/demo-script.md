# Portfolio demo script (3–5 minutes)

**Synthetic data only. Not affiliated with any real wellbeing services county. Not production-ready.**

GitHub presentation for people who will not run the stack: [`docs/walkthrough/`](walkthrough/README.md). This script is the **in-person** local run. Do not substitute a public Vercel/Render/Azure/GitHub Pages site.

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

1. Login as requester. Choose demo scenario **Määräaikainen ilman loppupäivää** or submit text **without** employee id / end date for määräaikainen / `kirjaaja`.
2. Show status **Odottaa täsmennystä** / `needs_clarification`, missing-field list, rule findings.
3. Explain: system routes to clarification, not silent approval.

## 3:00 — Timeout reconciliation (60 s)

1. Login as reviewer with a **ready** approved request (from happy path or pre-seeded).
2. Open submission / forward UI. Select demo-vikatila **Kadonnut vastaus onnistuneen käsittelyn jälkeen** (`lost-response`) and forward.
3. The mock stores the record and omits the HTTP body. The dispatcher looks up the same idempotency key **in that request** and the panel shows **Vastaanotettu** / a mock record id — not a parked **Tuntematon** badge.
4. Say explicitly: same key, one mock record; the mock still does not create an account.

A lingering `unknown` status is recovered in pytest (`test_stale_in_flight_is_recovered_as_unknown`). Do not invent that screen if the UI already reconciled. Alternative narration: run that test and describe the states from [`docs/walkthrough/05-timeout-reconciliation.md`](walkthrough/05-timeout-reconciliation.md).

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
