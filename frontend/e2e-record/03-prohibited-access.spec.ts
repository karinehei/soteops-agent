import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  apiForRole,
  csrfHeaders,
  getRequest,
  holdForReading,
  openRecordedSession,
  submitDemoScenario,
  waitForProcessingStatus,
  writeScenarioResult,
} from "./helpers";

const SCENARIO_ID = "03-prohibited-access";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);

test("03 prohibited access: policy finding, queue exclusion, API reject", async ({
  browser,
  playwright,
}) => {
  const requesterVideo = path.join(VIDEO_DIR, "requester.webm");
  const reviewerVideo = path.join(VIDEO_DIR, "reviewer-queue.webm");
  const requester = await openRecordedSession(browser, "requester", requesterVideo);
  let requestId = "";
  try {
    requestId = await submitDemoScenario(requester.page, "prohibited-role");
    await waitForProcessingStatus(requester.page, /Odottaa täsmennystä/);
    await expect(requester.page.getByTestId("rule-violations")).toContainText("Kielletty käyttöoikeus");
    await expect(requester.page.getByTestId("approval-eligibility")).toHaveCount(0);
    await expect(requester.page.getByTestId("approve-button")).toHaveCount(0);
    await holdForReading(requester.page);
  } finally {
    await requester.finalize();
  }

  const reviewer = await openRecordedSession(browser, "reviewer", reviewerVideo);
  try {
    await reviewer.page.goto("/review");
    await expect(reviewer.page.getByTestId("review-queue")).toBeVisible();
    await expect(reviewer.page.getByTestId(`request-card-${requestId}`)).toHaveCount(0);
    await holdForReading(reviewer.page);
  } finally {
    await reviewer.finalize();
  }

  const reviewerApi = await apiForRole(playwright, "reviewer");
  try {
    const current = await getRequest(reviewerApi, requestId);
    expect(current.status).toBe("needs_clarification");
    const headers = await csrfHeaders(reviewerApi);
    const approve = await reviewerApi.post(`/requests/${requestId}/approve`, {
      headers,
      data: {
        proposal_id: current.current_proposal.id,
        revision: current.revision,
        payload_hash: current.current_proposal.payload_hash,
        policy_version: current.current_proposal.policy_version,
      },
    });
    expect(approve.status()).toBe(409);
    const detail = (await approve.json()) as { detail: string };
    expect(detail.detail).toBe("Request is not awaiting review");
    const after = await getRequest(reviewerApi, requestId);
    expect(after.status).toBe("needs_clarification");
    expect(after.current_submission).toBeNull();
  } finally {
    await reviewerApi.dispose();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "prohibited-role",
    assertions: [
      "Requester UI shows Kielletty käyttöoikeus and no approve button",
      "Request id is absent from /review queue",
      "Reviewer POST /approve returns 409 Request is not awaiting review (API-only, not in video)",
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo, reviewerVideo],
    planned_gif: "docs/walkthrough/media/03-prohibited-access.gif",
    limitation:
      "The requester screen has no approve control. API 409 is recorded in this manifest, not in the video.",
    notes:
      "Video shows findings and queue exclusion only. Approve is rejected because the case is needs_clarification, so it is not awaiting review. The later policy-violation 409 is not reached on this fixture. Do not present a disabled button on the requester page.",
  });
});
