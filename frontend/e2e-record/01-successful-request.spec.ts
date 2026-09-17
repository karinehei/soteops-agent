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

const SCENARIO_ID = "01-successful-request";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);

test("01 successful request: create, review, simulated mock receive", async ({
  browser,
  playwright,
}) => {
  const requesterVideo = path.join(VIDEO_DIR, "requester.webm");
  const reviewerVideo = path.join(VIDEO_DIR, "reviewer.webm");
  const requester = await openRecordedSession(browser, "requester", requesterVideo);
  let requestId = "";
  try {
    requestId = await submitDemoScenario(requester.page, "complete-permanent");
    await waitForProcessingStatus(requester.page, /Odottaa tarkastusta/);
    await expect(requester.page.getByTestId("proposal-panel")).toBeVisible();
    await expect(requester.page.locator(".fake-label")).toContainText("SYNTEETTINEN FAKE-TARJOAJA");
    await expect(requester.page.getByTestId("approve-button")).toHaveCount(0);
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
    await expect(reviewer.page.getByTestId("approval-eligibility")).toContainText(
      "kelpaa hyväksyntään",
    );
    await holdForReading(reviewer.page);
    await reviewer.page.getByTestId("approve-button").click();
    await expect(reviewer.page.getByTestId("processing-status")).toContainText(
      /Hyväksytty, ei vielä lähetetty/,
    );
    await expect(reviewer.page.getByTestId("submission-panel")).toContainText(
      "ei luo tilejä eikä myönnä oikeuksia",
    );
    await reviewer.page.getByTestId("forward-button").click();
    await expect(reviewer.page.getByTestId("submission-panel")).toContainText(/Vastaanotettu/, {
      timeout: 30_000,
    });
    await expect(reviewer.page.getByTestId("submission-panel")).toContainText(/Mock-tietue/);
    await expect(reviewer.page.getByTestId("audit-timeline")).toContainText("Hyväksytty");
    await holdForReading(reviewer.page);
  } finally {
    await reviewer.finalize();
  }

  const reviewerApi = await apiForRole(playwright, "reviewer");
  try {
    const body = await getRequest(reviewerApi, requestId);
    expect(body.status).toBe("forwarded");
    expect(body.current_submission.status).toBe("accepted");
    expect(body.current_submission.downstream_reference).toBeTruthy();
    const lookup = await mockLookup(body.current_submission.idempotency_key);
    expect(lookup.stores_accounts).toBe(false);
    expect(lookup.record_id).toBe(body.current_submission.downstream_reference);
    const after = await mockRecords();
    expect(after.stores_accounts).toBe(false);
    expect(after.count).toBe(before.count + 1);
  } finally {
    await reviewerApi.dispose();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "complete-permanent",
    assertions: [
      "Requester submitted complete-permanent and reached ready_for_review",
      "Reviewer approved the exact proposal",
      "Forward created exactly one additional mock record",
      "Mock stores_accounts is false (simulated forwarding, not provisioning)",
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo, reviewerVideo],
    planned_gif: "docs/walkthrough/media/01-successful-request.gif",
    limitation: "",
    notes:
      "Simulated forwarding to the local mock integration. The mock stores a request record; it does not create accounts or grant access.",
  });
});
