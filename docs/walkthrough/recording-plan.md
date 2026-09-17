# Walkthrough recording plan

Animated GIFs for [`docs/walkthrough/`](README.md) must be recorded from the **actual local application**. Do not generate, mock, or composite screens. Do not record until this plan is followed.

Recordings replace a public visitor deployment. Do not stand up Vercel, Render, Neon, Azure hosting, GitHub Pages, or a public workspace in order to capture these clips.

## Environment (required)

All runs use synthetic seed data and deterministic fake providers.

| Setting | Required value |
| --- | --- |
| `LLM_PROVIDER` | `fake` |
| `EMBEDDING_PROVIDER` | `fake` |
| `AZURE_OPENAI_ENABLED` | `false` / unset |
| `ENVIRONMENT` | `local` (or Compose default) |
| `DEMO_AUTH_ENABLED` | `true` |
| Seed | `uv run soteops-seed` (or Compose API startup seed) |

Do not point `LLM_PROVIDER` or `EMBEDDING_PROVIDER` at `ollama` or `azure_openai`. Do not make paid or cloud model calls.

Start the **isolated recording stack** (does not reset the developer database):

```bash
uv run python scripts/walkthrough_record.py
uv run python scripts/walkthrough_record.py --scenario 01-successful-request
```

Details: [`recording.md`](recording.md). Ordinary E2E (`npm run test:e2e`) is unchanged.

GIF conversion (after capture, FFmpeg required):

```powershell
python scripts/walkthrough_gif.py
```

Waiting periods in the GIFs are shortened. GIF duration is not measured application latency.

For a live demo on the developer stack, `docker compose up --build` still uses `http://127.0.0.1:3000`.

### Capture rules

- Desktop viewport (about 1440×900). Keep the synthetic-data banner visible.
- Finnish UI copy as rendered. Do not overlay English captions that invent capabilities.
- Show the fake-provider label (`SYNTEETTINEN FAKE-TARJOAJA`) whenever a proposal explanation is in frame.
- Two personas need two browser profiles or a logout/login. Do not use a requester session to approve.
- If a step is not visible in the UI, stop. Use the test-evidence section instead of fabricating a screen.
- Write finished GIFs to `docs/walkthrough/media/` using the filenames below. Convert with `python scripts/walkthrough_gif.py`. Do not commit a GIF until the visible outcome matches this plan.

### Personas

Passwords are local demo credentials in `seed/identities.json` (also listed in `frontend/src/lib/demo-scenarios.ts`). They are not directory or Entra ID secrets.

| Role | Email | UI home |
| --- | --- | --- |
| Requester | `aino.esimerkki@demo.invalid` | `/requests`, `/requests/new` |
| Reviewer | `ville.valvoja@demo.invalid` | `/review`, `/review/{id}` |
| Operator | `outi.operaattori@demo.invalid` | `/requests` (all cases); may forward, cannot approve |

## Verified scenario table

| # | Candidate | Classification | Record? | Proposed file |
| --- | --- | --- | --- | --- |
| 1 | Successful request: create → prepare → authorized reviewer approves → mock receives | **Supported and recordable** | Yes | `media/01-successful-request.gif` |
| 2 | Missing information: missing end date → clarification → correction → resubmit | **Supported and recordable** | Yes | `media/02-missing-end-date.gif` |
| 3 | Prohibited access: deterministic policy violation → approval blocked | **Supported and recordable** | Yes | `media/03-prohibited-access.gif` |
| 4 | Conflicting instructions: conflicting evidence → manual review | **Supported and recordable** (verify sources in frame) | Yes, only if both conflict documents appear | `media/04-conflicting-instructions.gif` |
| 5 | Timeout recovery: unknown outcome → reconciliation → no duplicate mock record | **Supported and recordable** for in-dispatch reconciliation; lingering `unknown` is **implemented but test-only** | Yes, record the supported UI path only | `media/05-timeout-reconciliation.gif` |
| 6 | Approval invalidation: editing an eligible request invalidates its previous proposal/approval | **Supported and recordable** as a stale proposal during review; **not** edit-after-approve | Yes, use the stale-proposal path | `media/06-stale-proposal.gif` |

None of the six candidates are unimplemented. None are blocked by a known defect. Do not bypass edit locks to manufacture an after-approval invalidation clip.

---

## 1. Successful request

### Purpose

Show the full happy path: a complete synthetic request is prepared, an authorized reviewer approves the exact proposal snapshot, and the mock integration stores one request record (not an account).

### Classification

**Supported and recordable.**

### Personas and UI path

1. Login as requester (`/login`).
2. Home → labelled scenario **Täydellinen vakituinen pyyntö**, or open `/requests/new?scenario=complete-permanent`.
3. Submit **Lähetä valmisteltavaksi**. Land on `/requests/{id}`.
4. Wait until processing status is **Odottaa tarkastusta** (`ready_for_review`).
5. Logout. Login as reviewer. Open `/review/{id}` (also listed on `/review` while `ready_for_review` / `in_review`).
6. **Aloita tarkastus**. Confirm **Ehdotus kelpaa hyväksyntään nykyisten sääntöjen mukaan.**
7. **Hyväksy tarkka ehdotus**. Status becomes **Hyväksytty, ei vielä lähetetty** with a pending submission.
8. Leave demo-vikatila on **Onnistuminen**. **Lähetä / yritä uudelleen**.
9. Submission panel shows **Vastaanotettu**, a **Mock-tietue** id, and the idempotency key. Audit includes **Hyväksytty**.

### Expected visible outcome

- Fake-provider label on the proposal.
- Reviewer, not requester, performs approve.
- Mock copy: *Mock-integraatio tallentaa pyyntötietueen. Se ei luo tilejä eikä myönnä oikeuksia.*
- After forward: `forwarded` / **Välitetty** and submission `accepted`.

### Fixture

`DEMO_SCENARIOS` id `complete-permanent` (`frontend/src/lib/demo-scenarios.ts`): `demo-hr-testi` + `lukuoikeus` + `EMP-1001` + start `2026-10-01`, no end date. Policy `policy-v1` allows that combination.

### APIs

`POST /requests` → `POST /requests/{id}/review` → `POST /requests/{id}/approve` (proposal id, revision, `payload_hash`, `policy_version`) → `POST /requests/{id}/forward`.

### Tests

- Playwright: `frontend/e2e/happy-path.spec.ts` (`requester submit → reviewer approve → forward shows mock record`)
- pytest: `backend/tests/test_access_requests.py::test_reviewer_queue_and_happy_path_approve`
- pytest: `backend/tests/test_forwarding.py::test_successful_forward_creates_one_mock_record`

### Filename

`docs/walkthrough/media/01-successful-request.gif`

### Blockers

None for this path.

---

## 2. Missing information

### Purpose

Show that a määräaikainen / `kirjaaja` request without an end date is routed to clarification, not silent approval, and that the requester can correct and resubmit.

### Classification

**Supported and recordable.** Playwright covers create → clarification. Correction + save is implemented in the requester edit form (`PATCH /requests/{id}` immediately re-runs preparation). A separate **Lähetä uudelleen valmisteltavaksi** button exists for `needs_clarification` (`POST /requests/{id}/resubmit`).

### Personas and UI path

1. Login as requester.
2. Scenario **Määräaikainen ilman loppupäivää** (`/requests/new?scenario=temporary-missing-end`).
3. Submit. Status **Odottaa täsmennystä**. Findings list **Loppupäivä** and **Määräaikainen vaatii loppupäivän**. Approval-eligibility card is not shown to the requester; there is no approve control on this page.
4. **Muokkaa ja täsmennä**. Set **Loppupäivä** (for example `2026-12-31`). Optionally mention the date in the original text. **Tallenna muutokset**.
5. Preparation runs again. Expected status **Odottaa tarkastusta** if the date is present and no other violations remain.
6. Optional, not required for the GIF: **Lähetä uudelleen valmisteltavaksi** is the no-edit resubmit control; after a successful save it is unnecessary.

### Expected visible outcome

- First proposal: `needs_clarification`, missing `end_date`, violation `temporary_requires_end_date`.
- After correction: new revision, previous proposal invalidated (notice may say a previous approval is no longer valid even when none existed — that is current UI copy), status `ready_for_review`.
- The GIF must show the corrected end date (`2026-12-31`), empty findings copy (**Ei puuttuvia kenttiä** / **Ei puuttuvia kenttiä eikä sääntöhavaintoja**), **and** the resulting status (**Odottaa tarkastusta**). Scroll those into the recorded viewport; do not treat off-screen DOM as visual evidence.
- Do not show a reviewer approve unless that is a separate clip. This scenario stops at successful resubmit.

### Fixture

`temporary-missing-end`: `kirjaaja` + `maaraaikainen` + `EMP-2002` + start `2026-11-01` + `end_date: null`. Policy treats `kirjaaja` as a temporary access role (`seed/policy/v1.json` `temporary_access_roles`).

### APIs

`POST /requests` → `PATCH /requests/{id}` (edit + prepare). Optional `POST /requests/{id}/resubmit`.

### Tests

- Playwright: `frontend/e2e/demo-scenarios.spec.ts` (`demo scenario: temporary-missing-end`) — asserts **Odottaa täsmennystä** and no `approval-eligibility` on the requester page
- Playwright recording: `frontend/e2e-record/02-missing-end-date.spec.ts` — fills the end date, re-prepares, and asserts **Odottaa tarkastusta** plus empty findings in the recorded viewport
- pytest: `backend/tests/test_rules.py::test_temporary_access_requires_end_date`
- pytest: `backend/tests/test_access_requests.py::test_resubmit_creates_new_revision`

### Filename

`docs/walkthrough/media/02-missing-end-date.gif`

### Blockers

None. If save does not clear the missing-field finding, do not keep a GIF that implies it did.

---

## 3. Prohibited access

### Purpose

Show a deterministic policy block (`tuotanto-superadmin`). The model does not grant access. Approval is not available.

### Classification

**Supported and recordable.**

### Personas and UI path

1. Login as requester.
2. Scenario **Kielletty käyttöoikeus** (`/requests/new?scenario=prohibited-role`).
3. Submit. Status **Odottaa täsmennystä**. Findings: **Kielletty käyttöoikeus**.
4. This case does **not** appear on `/review` (`GET /review/queue` only lists `ready_for_review` and `in_review`).
5. Optional but useful: copy `/review/{id}` as reviewer. Eligibility: **Ehdotus ei kelpaa hyväksyntään ennen puutteiden korjausta.** **Hyväksy tarkka ehdotus** is disabled. Do not try to force-enable it.

Do not claim the reviewer queue contains prohibited cases. Do not show a successful approve.

### Expected visible outcome

- `needs_clarification`
- `rule_violations` includes `prohibited_role`
- Approve control absent (requester) or disabled (reviewer-by-URL)
- API `POST /requests/{id}/approve` returns `409` (`Request is not awaiting review`) because the case stays `needs_clarification` and never enters the review queue. The later `Policy violations must be resolved before approval` 409 is not reached on this fixture. That API 409 is capture-manifest evidence; it is **not** in the GIF.

The GIF must scroll until the full **Kielletty käyttöoikeus** finding and its explanation are in the 1440×900 viewport, hold that view long enough to read, and use it as the poster. If the reviewer queue is included, show the request identity first so an empty queue (or the absence of EMP-3003 / `tuotanto-superadmin`) is understandable. Another employee’s row alone does not demonstrate exclusion. The API 409 stays capture-manifest / test evidence; do not fabricate a UI error or claim the later policy-violation guard was exercised.

### Fixture

`prohibited-role`: `requested_access_role: tuotanto-superadmin` (`seed/policy/v1.json` `prohibited_access_roles`).

### APIs

`POST /requests` (prepare → `needs_clarification`). Approve is rejected while violations remain.

### Tests

- Playwright: `frontend/e2e/demo-scenarios.spec.ts` (`demo scenario: prohibited-role`)
- pytest: `backend/tests/test_rules.py::test_prohibited_role_cannot_be_approved`
- pytest: `backend/tests/test_access_requests.py::test_policy_violation_cannot_be_approved`

### Filename

`docs/walkthrough/media/03-prohibited-access.gif`

### Blockers

None. Reviewer queue omission is intended routing, not a defect. Record the requester findings (and optionally the disabled reviewer approve via direct URL).

---

## 4. Conflicting instructions

### Purpose

Show that retrieval can surface two contradictory **SYNTHETIC** instruction versions. Retrieved text is evidence, not authorization. Deterministic rules still decide eligibility.

### Classification

**Supported and recordable**, with a pre-record verification gate.

There is no separate `conflict` request status. The labelled demo fixture is also missing an end date, so preparation ends in `needs_clarification`, not `ready_for_review`. “Manual review” here means: both instruction cards are shown to a human; rules are not changed by retrieval. The case is **not** placed on the reviewer queue.

### Personas and UI path

1. Login as requester.
2. Scenario **Ristiriitaiset ohjeet** (`/requests/new?scenario=conflicting-instructions`).
3. Submit. Status **Odottaa täsmennystä** (missing end date / `temporary_requires_end_date`).
4. Scroll **Ohjelähteet ja versiot**.
5. **Gate:** Playwright must scroll each card into the recorded viewport and assert both titles (or `document_id`s) **in frame**. DOM-only assertions do not satisfy the GIF. Show A then B sequentially, with enough excerpt text to see the difference. A longer GIF or clearly linked parts is allowed. Disclose `RETRIEVAL_TOP_K=8` when that override was used, and state whether it applied to the entire recording stack or only this scenario.
   - `Ristiriita A: kirjaaja ilman loppupäivää (SYNTHETIC)` (`SYN-OHJE-RISTIRIITA-A-01-v1`)
   - `Ristiriita B: kirjaaja vaatii loppupäivän (SYNTHETIC)` (`SYN-OHJE-RISTIRIITA-B-01-v1`)
6. Each source card includes *Ohje on näyttöä tarkastajalle, ei valtuutus.*
7. Optional: open `/review/{id}` as reviewer to show eligibility blocked. Do not invent a queue entry.

### Expected visible outcome

- Conflicting SYNTHETIC excerpts A and B in source references
- Rules still require an end date; approval remains blocked
- Fake-provider explanation may mention conflicting instructions; that text is not a policy decision

### Fixture

`conflicting-instructions` plus corpus documents in `seed/instructions.json` (topics `conflict`). Retrieval test query is `kirjaaja loppupäivä demo-hr-testi` at `top_k=8`. Default app `RETRIEVAL_TOP_K` is **4** (`.env.example`, Compose default). The recording spec scrolls both documents into view. Clarification is caused by the missing end date; do not claim automatic conflict detection.

### APIs

`POST /requests` (graph node `retrieve_instructions` → persist). No special conflict endpoint.

### Tests

- Playwright: `frontend/e2e/demo-scenarios.spec.ts` (`demo scenario: conflicting-instructions`) — status only
- pytest: `backend/tests/test_retrieval.py::test_conflicting_current_instructions_are_both_retrieved` (`top_k=8`)
- pytest: `backend/tests/test_seed_file.py` (at least two `conflict` documents)
- Held-out eval: `seed/evaluation/cases.json` `eval-025` (`top_k=8`)

### Filename

`docs/walkthrough/media/04-conflicting-instructions.gif`

### Blockers

If only one conflict document (or neither) appears at `RETRIEVAL_TOP_K=4`, **do not record a fabricated pair**. The 04 recapture used `RETRIEVAL_TOP_K=8` for that isolated recording stack because both sources were absent at 4. Original captures for 01, 05, and 06 also used 8. Recaptures for 02 and 03 used 4. The published GIF shows **Ristiriita A** then **Ristiriita B** in frame.

---

## 5. Timeout recovery

### Purpose

Show that a lost downstream response is reconciled with the same idempotency key and does not create a second mock record.

### Classification

**Supported and recordable** for the UI that exists today.

**Implemented but test-only:** leaving the request on screen in submission status `unknown` / phase **Alasvirran tulos tuntematon**. The dispatcher looks up the idempotency key in the **same** `POST /requests/{id}/forward` call after a `lost-response` (HTTP 204). Playwright therefore expects **Mock-tietue** or **Vastaanotettu** after one click, not a pause on `unknown`.

`recover_stale_in_flight` (stale `in_flight` → `unknown`) has no demo button. Do not wait, inject DB rows, or crop a pytest log and present it as the UI.

### Personas and UI path

1. Follow scenario 1 through approve, using fixture `downstream-timeout` (`/requests/new?scenario=downstream-timeout`) so the labelled demo matches the clip.
2. As reviewer (or operator), open the submission panel.
3. Demo-vikatila: **Kadonnut vastaus onnistuneen käsittelyn jälkeen** (`lost-response`).
4. **Lähetä / yritä uudelleen**.
5. After the request returns: submission **Vastaanotettu**, one **Mock-tietue** id, same idempotency key `{request_id}:{payload_hash}`. Attempt count is typically `1` because reconcile happens inside that dispatch.
6. The forward button is then disabled (`accepted`). A second click is not available in the UI — that is the lock after success, not proof of a second record.

Do not select `lost-response` and then claim the visible status stayed **Tuntematon tulos**. That is not what this control does.

### Expected visible outcome

- One mock record id
- Idempotency key unchanged
- Copy that the mock does not create accounts
- Not a two-step “unknown, then retry” screen recording

### Fixture

`downstream-timeout` (complete `lukuoikeus` request, `EMP-5005`). Fault header `X-Mock-Fault: lost-response` is local-only (`ENVIRONMENT` in `local` / `test` / `ci` / `demo`).

### APIs

`POST /requests/{id}/forward` with `{ "demo_fault": "lost-response" }`. Mock `POST /requests` stores the record then returns 204. Monolith `GET /requests?idempotency_key=` reconciles before the HTTP response to the browser.

### Tests

- Playwright: `frontend/e2e/demo-scenarios.spec.ts` (`downstream lost-response demo reconciles after forward`)
- pytest: `backend/tests/test_forwarding.py::test_commit_then_timeout_is_reconciled`
- pytest: `backend/tests/test_forwarding.py::test_stale_in_flight_is_recovered_as_unknown` (lingering `unknown`; not a UI path)
- pytest: `backend/tests/test_forwarding.py::test_concurrent_dispatchers_do_not_duplicate`

### Filename

`docs/walkthrough/media/05-timeout-reconciliation.gif`

### Blockers

Do not fabricate an `unknown` badge. If a future change returns `unknown` to the browser before reconcile, re-verify this plan before recording.

---

## 6. Approval invalidation (stale proposal)

### Purpose

Show that a reviewer approves a **specific** proposal snapshot. Editing the request while it is still eligible for review invalidates that snapshot. A stale approve is rejected.

### Classification

**Supported and recordable** using edit during `ready_for_review` / `in_review`.

**Not a supported UI path:** edit after a successful approve. On approve the server inserts a `pending` submission in the same transaction. Edits are blocked while submission is `pending`, `in_flight`, or `unknown`, and while status is `forwarding` or `forwarded`. The requester edit panel is not shown for `approved`. Do not disable those checks to film “edit after approval”.

### Personas and UI path (two browsers)

1. Requester: scenario **Hyväksynnän ohitusyritys** (`/requests/new?scenario=approval-bypass`). Submit. Wait for **Odottaa tarkastusta**.
2. Reviewer: `/review/{id}` → **Aloita tarkastus**. Leave this page open (it still holds the old `proposal_id` / hash).
3. Requester: `/requests/{id}` → **Muokkaa ja täsmennä** → change original text (Playwright uses a full replacement string for `EMP-6006`) → **Tallenna muutokset**.
4. Requester sees `data-testid="invalidation-notice"` (*Pyyntöä muokattiin. Edellinen hyväksyntä ei ole enää voimassa — tarvitaan uusi tarkastus.*). Audit may include **Edellinen ehdotus mitätöity**.
5. Reviewer (stale page): **Hyväksy tarkka ehdotus**. Error `data-testid="review-error"` contains a stale/409/proposal/revision message (API detail is currently English, e.g. `Stale proposal` / `Stale revision`).
6. Do not show a green approved state from that click.

### Expected visible outcome

- New revision and new current proposal id
- Previous proposal `invalidated_at` set (visible only via later review of a new proposal / audit, not as a separate admin screen)
- Stale approve fails in the reviewer UI
- After reload, reviewer would need to start from the new snapshot

### Fixture

`approval-bypass` (otherwise complete `lukuoikeus` request, `EMP-6006`).

### APIs

`PATCH /requests/{id}` while status is in `EDITABLE_STATUSES` and `submission_blocks_edits` is false. `POST /requests/{id}/approve` with the old proposal id / hash / revision → `409`.

`PATCH` after approve + pending submission → `409` (`Edits are blocked while a submission is pending…`). That lock is the control; it is not a recording target for invalidation.

### Tests

- Playwright: `frontend/e2e/stale-approve.spec.ts` (`stale approve after requester edit is rejected in UI`)
- pytest: `backend/tests/test_access_requests.py::test_edit_invalidates_previous_proposal_and_stale_approval`
- pytest: `backend/tests/test_forwarding.py::test_pending_submission_blocks_edits`
- pytest: `backend/tests/test_forwarding.py::test_stale_proposal_cannot_submit`

### Filename

`docs/walkthrough/media/06-stale-proposal.gif`

### Blockers

Do not record edit-after-approve. Use this stale-proposal path. The invalidation notice mentions “hyväksyntä” even when no approval existed; that is current copy, not a reason to skip the clip.
