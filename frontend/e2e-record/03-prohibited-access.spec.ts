import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  apiForRole,
  csrfHeaders,
  expectEvidenceInViewport,
  getRequest,
  holdForReading,
  openRecordedSession,
  revealInViewport,
  submitDemoScenario,
  waitForProcessingStatus,
  writeScenarioResult,
} from "./helpers";

const SCENARIO_ID = "03-prohibited-access";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);
const retrievalTopK = process.env.WALKTHROUGH_RETRIEVAL_TOP_K ?? "4";

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
    await expect(requester.page.getByTestId("rule-violations")).toContainText(
      "Kielletty käyttöoikeus",
    );
    await expect(requester.page.getByTestId("approval-eligibility")).toHaveCount(0);
    await expect(requester.page.getByTestId("approve-button")).toHaveCount(0);
    await requester.page.evaluate(() => window.scrollTo(0, 0));
    await expect(requester.page.getByTestId("proposal-panel")).toContainText("EMP-3003");
    await expect(requester.page.getByTestId("proposal-panel")).toContainText("tuotanto-superadmin");
    await holdForReading(requester.page, 1_600);
    const finding = requester.page.getByTestId("rule-violations");
    await revealInViewport(finding);
    await expect(finding).toContainText("Kielletty käyttöoikeus");
    await expectEvidenceInViewport(requester.page, finding, 80);
    await holdForReading(requester.page, 2_800);
  } finally {
    await requester.finalize();
  }

  const reviewer = await openRecordedSession(browser, "reviewer", reviewerVideo);
  try {
    await reviewer.page.goto("/review");
    await expect(reviewer.page.getByTestId("review-queue")).toBeVisible();
    await expect(reviewer.page.getByTestId(`request-card-${requestId}`)).toHaveCount(0);
    await expect(reviewer.page.getByTestId("review-queue")).not.toContainText("EMP-3003");
    await expect(reviewer.page.getByTestId("review-queue")).not.toContainText("tuotanto-superadmin");
    await holdForReading(reviewer.page, 2_200);
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
      "Kielletty käyttöoikeus finding was scrolled into the recorded viewport",
      "Request id and EMP-3003 are absent from /review queue",
      "Reviewer POST /approve returns 409 Request is not awaiting review (API-only, not in video)",
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo, reviewerVideo],
    planned_gif: "docs/walkthrough/media/03-prohibited-access.gif",
    limitation:
      "The requester screen has no approve control. API 409 is recorded in the capture result, not in the video. " +
      "The later policy-violation 409 is not reached on this fixture.",
    notes:
      `Video shows identity (EMP-3003 / tuotanto-superadmin), the Kielletty finding in viewport, ` +
      `and queue exclusion of that identity. Recapture stack RETRIEVAL_TOP_K=${retrievalTopK}; ` +
      `this scenario does not depend on retrieval top_k.`,
  });
});
