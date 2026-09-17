import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  apiForRole,
  getRequest,
  holdForReading,
  openRecordedSession,
  submitDemoScenario,
  waitForProcessingStatus,
  writeScenarioResult,
} from "./helpers";

const SCENARIO_ID = "06-stale-proposal";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);

test("06 stale proposal: requester edit rejects reviewer approve, no submission", async ({
  browser,
  playwright,
}) => {
  const requesterVideo = path.join(VIDEO_DIR, "requester.webm");
  const reviewerVideo = path.join(VIDEO_DIR, "reviewer.webm");
  const requester = await openRecordedSession(browser, "requester", requesterVideo);
  let requestId = "";
  try {
    requestId = await submitDemoScenario(requester.page, "approval-bypass");
    await waitForProcessingStatus(requester.page, /Odottaa tarkastusta/);

    const reviewer = await openRecordedSession(browser, "reviewer", reviewerVideo);
    try {
      await reviewer.page.goto(`/review/${requestId}`);
      await waitForProcessingStatus(reviewer.page, /Odottaa tarkastusta/);
      await reviewer.page.getByRole("button", { name: "Aloita tarkastus" }).click();
      await expect(reviewer.page.getByTestId("approve-button")).toBeEnabled();
      await holdForReading(reviewer.page);

      await requester.page.goto(`/requests/${requestId}`);
      await requester.page.getByRole("button", { name: "Muokkaa ja täsmennä" }).click();
      await requester.page
        .getByLabel("Alkuperäinen teksti")
        .fill(
          "Päivitetty synteettinen teksti EMP-6006 demo-hr-testi lukuoikeus vakituinen demo-osasto 2026-10-01.",
        );
      await requester.page.getByRole("button", { name: "Tallenna muutokset" }).click();
      await expect(requester.page.getByTestId("invalidation-notice")).toBeVisible();
      await waitForProcessingStatus(requester.page, /Odottaa tarkastusta/);
      await holdForReading(requester.page);

      await reviewer.page.getByTestId("approve-button").click();
      await expect(reviewer.page.getByTestId("review-error")).toContainText(
        /Stale|vanhentunut|409|proposal|revision/i,
      );
      await expect(reviewer.page.getByTestId("processing-status")).not.toContainText(/Hyväksytty/);
      await holdForReading(reviewer.page);
    } finally {
      await reviewer.finalize();
    }
  } finally {
    await requester.finalize();
  }

  const reviewerApi = await apiForRole(playwright, "reviewer");
  try {
    const body = await getRequest(reviewerApi, requestId);
    expect(body.status).not.toBe("approved");
    expect(body.current_submission).toBeNull();
  } finally {
    await reviewerApi.dispose();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "approval-bypass",
    assertions: [
      "Reviewer started review on the original proposal",
      "Requester edit while in_review invalidated that proposal",
      "Stale approve was rejected in the reviewer UI",
      "No downstream submission was created by the stale attempt",
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo, reviewerVideo],
    planned_gif: "docs/walkthrough/media/06-stale-proposal.gif",
    limitation:
      "Edit after a successful approve remains locked by the pending submission. This clip is stale-proposal during review only.",
    notes: "Two authenticated contexts. Edit locks after approval were not bypassed.",
  });
});
