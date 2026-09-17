# 6. Stale proposal after edit

Show that a reviewer approves a **specific** proposal snapshot. If the requester edits while the case is still in review, that snapshot is no longer current and a stale approve is rejected.

**Persona and start:** Two sessions. Requester `aino.esimerkki@demo.invalid` opens **Hyväksynnän ohitusyritys** (`/requests/new?scenario=approval-bypass`: `EMP-6006`). Reviewer `ville.valvoja@demo.invalid` starts review and **leaves that page open**.

![Requester request ready for review, reviewer opens it, requester edits, reviewer stale approve is rejected](media/06-stale-proposal.gif)

[Static poster](media/06-stale-proposal-poster.png)

## What the GIF shows

1. Requester reaches **Odottaa tarkastusta**.
2. Reviewer opens `/review/{id}`, clicks **Aloita tarkastus** (**Tarkastuksessa**), eligibility still looks fine on that tab.
3. Requester **Muokkaa ja täsmennä**, saves new original text. Invalidation notice appears.
4. Reviewer clicks **Hyväksy tarkka ehdotus** on the **un-refreshed** page. `review-error` shows a stale/409 message (API detail is English, e.g. `Stale proposal`). Status does **not** become **Hyväksytty**.

This is **during review**. It is not an edit-after-approval path.

## What this recording demonstrates

Approval is bound to proposal id, revision, payload hash, and policy version. An edit creates a new proposal and invalidates the previous one. The open reviewer tab still holds the old snapshot, so approve fails.

After a **successful** approve, a `pending` submission is created in the same transaction. The requester edit panel is not shown for `approved`, and the server rejects edits while submission is `pending` / `in_flight` / `unknown` (and while status is `forwarding` or `forwarded`). This walkthrough does not bypass that lock.

The invalidation notice mentions *Edellinen hyväksyntä ei ole enää voimassa* even when no approval existed yet; that is the same current copy as in scenario 02.

## Automated checks (not only the GIF)

- Playwright: [`frontend/e2e/stale-approve.spec.ts`](../../frontend/e2e/stale-approve.spec.ts)
- pytest: [`test_edit_invalidates_previous_proposal_and_stale_approval`](../../backend/tests/test_access_requests.py)
- pytest (lock after approve): [`test_pending_submission_blocks_edits`](../../backend/tests/test_forwarding.py)
- pytest: [`test_stale_proposal_cannot_submit`](../../backend/tests/test_forwarding.py)

## Limitations

The stale reviewer tab may still show a green eligibility card because it was not reloaded; the visible control is the error, not a successful approve. Fake providers. Waiting periods shortened.

## Implementation

- Fixture: [`frontend/src/lib/demo-scenarios.ts`](../../frontend/src/lib/demo-scenarios.ts) (`approval-bypass`)
- Stale 409: [`backend/app/services/approvals.py`](../../backend/app/services/approvals.py)
- Edit lock: [`backend/app/services/forwarding.py`](../../backend/app/services/forwarding.py) (`submission_blocks_edits`), [`frontend/src/components/RequestDetailView.tsx`](../../frontend/src/components/RequestDetailView.tsx)
- Reviewer error UI: [`frontend/src/components/ReviewActions.tsx`](../../frontend/src/components/ReviewActions.tsx)

[Walkthrough overview](README.md) · Previous: [Lost-response reconciliation](05-timeout-reconciliation.md)
