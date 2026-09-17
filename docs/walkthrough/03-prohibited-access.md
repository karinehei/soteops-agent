# 3. Prohibited access

**Status:** supported and recorded. Local capture, fake providers, installed Chrome.

![Prohibited access](media/03-prohibited-access.gif)

**Caption:** Requester identity EMP-3003 / `tuotanto-superadmin`, then the full **Kielletty käyttöoikeus** finding in frame, then an empty reviewer queue (**Jono tyhjä**). The overlay names EMP-3003 so the empty queue is exclusion of this request, not a generic idle screen. This video does not show an API rejection.

The tested `POST /approve` 409 detail was **Request is not awaiting review** (case stayed `needs_clarification`). It did not exercise the later policy-violation guard. Waiting periods are shortened; GIF duration is not measured application latency.

## What you would see

1. Requester starts **Kielletty käyttöoikeus** (`/requests/new?scenario=prohibited-role`).
2. Status **Odottaa täsmennystä**. Finding **Kielletty käyttöoikeus**.
3. The case is **not** listed on `/review` (queue is `ready_for_review` / `in_review` only). The isolated recapture queue is empty, which excludes EMP-3003.
4. Opening `/review/{id}` as reviewer (direct URL) shows **Ehdotus ei kelpaa hyväksyntään** and a disabled **Hyväksy tarkka ehdotus**. That direct-URL screen is **not** in this GIF.

This walkthrough does not show a successful approve of a prohibited role. That outcome is not implemented.

## Personas

Requester for findings; optional reviewer-by-URL for the disabled approve control.

## Evidence

- Playwright: `frontend/e2e/demo-scenarios.spec.ts` (`prohibited-role`)
- pytest: `test_prohibited_role_cannot_be_approved`, `test_policy_violation_cannot_be_approved`

Recording steps: [`recording-plan.md`](recording-plan.md) §3.
