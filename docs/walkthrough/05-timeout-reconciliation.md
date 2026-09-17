# 5. Lost-response reconciliation

Show a **simulated** lost downstream response that is reconciled **inside the same forwarding call**. The UI reaches **Vastaanotettu** without a parked unknown screen and without a second forward click.

**Persona and start:** Requester creates **Alasvirran timeout onnistuneen käsittelyn jälkeen** (`/requests/new?scenario=downstream-timeout`: `EMP-5005`). Reviewer approves, sets demo fault **Kadonnut vastaus onnistuneen käsittelyn jälkeen**, then forwards once.

![Reviewer forwards with lost-response demo fault and the submission panel shows Vastaanotettu and one mock record](media/05-timeout-reconciliation.gif)

[Static poster](media/05-timeout-reconciliation-poster.png)

## What the GIF shows

1. A complete request is prepared and the reviewer approves the proposal.
2. Demo-vikatila is set to **Kadonnut vastaus onnistuneen käsittelyn jälkeen** (`lost-response`).
3. One **Lähetä / yritä uudelleen**. Submission **Tila** becomes **Vastaanotettu**; **Mock-tietue** and **Idempotenssiavain** are shown. Overlay: simulated lost response; automatic reconciliation.
4. There is no intermediate **Tuntematon tulos** / **Alasvirran tulos tuntematon** screen and no manual retry in this clip.

## What this recording demonstrates

The mock stores the record, then omits the HTTP body (204). The monolith looks up the same idempotency key `{request_id}:{payload_hash}` before returning to the browser. Retries would reuse that key; after `accepted` the UI disables further forward clicks (success lock, not a second-record proof).

**Exactly one mock record** for that key is a **capture assertion** (lookup by idempotency key after the click), not something the visible id alone proves.

## Automated checks (not only the GIF)

- Playwright: [`frontend/e2e/demo-scenarios.spec.ts`](../../frontend/e2e/demo-scenarios.spec.ts) (`downstream lost-response demo reconciles after forward`)
- pytest: [`test_commit_then_timeout_is_reconciled`](../../backend/tests/test_forwarding.py)
- pytest: [`test_concurrent_dispatchers_do_not_duplicate`](../../backend/tests/test_forwarding.py)
- pytest (not UI): [`test_stale_in_flight_is_recovered_as_unknown`](../../backend/tests/test_forwarding.py) — lingering `unknown` recovery; no demo button

## Limitations

`recover_stale_in_flight` has no demo control. Do not read this GIF as a two-step “unknown, then retry” flow. Fake providers. Waiting periods shortened.

## Implementation

- Fixture: [`frontend/src/lib/demo-scenarios.ts`](../../frontend/src/lib/demo-scenarios.ts) (`downstream-timeout`)
- Dispatcher + reconcile: [`backend/app/services/forwarding.py`](../../backend/app/services/forwarding.py)
- Demo fault control: [`frontend/src/components/SubmissionPanel.tsx`](../../frontend/src/components/SubmissionPanel.tsx)
- Mock 204 / idempotency: [`mock-integration/mock_integration/main.py`](../../mock-integration/mock_integration/main.py)

[Walkthrough overview](README.md) · Previous: [Conflicting instructions](04-conflicting-instructions.md) · Next: [Stale proposal](06-stale-proposal.md)
