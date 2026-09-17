import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  apiForRole,
  getRequest,
  holdForReading,
  mockLookup,
  mockRecords,
  openRecordedSession,
  submitDemoScenario,
  waitForProcessingStatus,
  writeScenarioResult,
} from "./helpers";

const SCENARIO_ID = "05-timeout-reconciliation";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);

test("05 lost-response: one-click forward reconciles to a single mock record", async ({
  browser,
  playwright,
}) => {
  const requesterVideo = path.join(VIDEO_DIR, "requester.webm");
  const reviewerVideo = path.join(VIDEO_DIR, "reviewer.webm");
  const requester = await openRecordedSession(browser, "requester", requesterVideo);
  let requestId = "";
  try {
    requestId = await submitDemoScenario(requester.page, "downstream-timeout");
    await waitForProcessingStatus(requester.page, /Odottaa tarkastusta/);
    await holdForReading(requester.page);
  } finally {
    await requester.finalize();
  }

  const before = await mockRecords();
  const reviewer = await openRecordedSession(browser, "reviewer", reviewerVideo);
  try {
    await reviewer.page.goto(`/review/${requestId}`);
    await waitForProcessingStatus(reviewer.page, /Odottaa tarkastusta/);
    await reviewer.page.getByRole("button", { name: "Aloita tarkastus" }).click();
    await reviewer.page.getByTestId("approve-button").click();
    await expect(reviewer.page.getByTestId("forward-button")).toBeEnabled();
    await reviewer.page.locator("#demo-fault").selectOption("lost-response");
    await expect(reviewer.page.locator("#demo-fault")).toHaveValue("lost-response");
    await holdForReading(reviewer.page);
    await reviewer.page.getByTestId("forward-button").click();
    await expect(reviewer.page.getByTestId("submission-panel")).toContainText(/Vastaanotettu/, {
      timeout: 30_000,
    });
    await expect(reviewer.page.getByTestId("processing-status")).not.toContainText(/tuntematon/i);
    await expect(reviewer.page.getByTestId("submission-panel")).toContainText(/Mock-tietue/);
    await holdForReading(reviewer.page);
  } finally {
    await reviewer.finalize();
  }

  const reviewerApi = await apiForRole(playwright, "reviewer");
  try {
    const body = await getRequest(reviewerApi, requestId);
    expect(body.status).toBe("forwarded");
    expect(body.current_submission.status).toBe("accepted");
    expect(body.current_submission.attempt_count).toBe(1);
    const lookup = await mockLookup(body.current_submission.idempotency_key);
    expect(lookup.stores_accounts).toBe(false);
    expect(lookup.record_id).toBe(body.current_submission.downstream_reference);
    const after = await mockRecords();
    const matching = after.records.filter(
      (item) => item.idempotency_key === body.current_submission.idempotency_key,
    );
    expect(matching).toHaveLength(1);
    expect(after.count).toBe(before.count + 1);
  } finally {
    await reviewerApi.dispose();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "downstream-timeout",
    assertions: [
      "lost-response demo fault selected before a single forward click",
      "UI reached Vastaanotettu without a parked unknown screen",
      "Exactly one mock record exists for the idempotency key",
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo, reviewerVideo],
    planned_gif: "docs/walkthrough/media/05-timeout-reconciliation.gif",
    limitation:
      "The mock stores the record then omits the HTTP body (204). The monolith looks up the same idempotency key in that same forward call. No intermediate unknown screen is shown.",
    notes:
      "Simulated lost response on the local mock. Reconciliation is in-dispatch. The mock still does not provision accounts.",
  });
});
