# 1. Successful request

**Status:** supported and recorded. Local capture, fake providers, installed Chrome.

![Successful request](media/01-successful-request.gif)

**Caption:** Requester prepares a complete request; reviewer approves the exact proposal; mock integration stores one record. **Mock record received — no account provisioned.** Waiting periods are shortened; GIF duration is not measured application latency.

## What you would see

1. Requester starts **Täydellinen vakituinen pyyntö** (`/requests/new?scenario=complete-permanent`).
2. After **Lähetä valmisteltavaksi**, `/requests/{id}` shows extracted fields, empty findings, SYNTHETIC citations, and the fake-provider label. Status **Odottaa tarkastusta**.
3. Reviewer opens `/review/{id}`, starts review, sees **Ehdotus kelpaa hyväksyntään nykyisten sääntöjen mukaan.**
4. **Hyväksy tarkka ehdotus**, then **Lähetä / yritä uudelleen** (demo fault: success).
5. Submission panel: **Vastaanotettu**, a mock record id, and an idempotency key.

## Personas

Requester `aino.esimerkki@demo.invalid`, then reviewer `ville.valvoja@demo.invalid`. A requester session cannot approve.

## Evidence

- Playwright: `frontend/e2e/happy-path.spec.ts`
- pytest: `test_reviewer_queue_and_happy_path_approve`, `test_successful_forward_creates_one_mock_record`

Recording steps: [`recording-plan.md`](recording-plan.md) §1.
