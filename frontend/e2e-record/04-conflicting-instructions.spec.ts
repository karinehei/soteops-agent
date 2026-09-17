import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  CONFLICT_DOC_A,
  CONFLICT_DOC_B,
  expectEvidenceInViewport,
  holdForReading,
  openRecordedSession,
  revealInViewport,
  submitDemoScenario,
  waitForProcessingStatus,
  writeScenarioResult,
} from "./helpers";

const SCENARIO_ID = "04-conflicting-instructions";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);
const retrievalTopK = process.env.WALKTHROUGH_RETRIEVAL_TOP_K ?? "4";

test("04 conflicting instructions: both SYNTHETIC sources if retrieved", async ({ browser }) => {
  if (process.env.WALKTHROUGH_CONFLICT_RECORDABLE === "0") {
    writeScenarioResult({
      id: SCENARIO_ID,
      fixture: "conflicting-instructions",
      assertions: [
        "Both conflict instruction documents must appear in the recorded viewport",
      ],
      assertions_passed: false,
      outcome: "blocked",
      video_segments: [],
      planned_gif: "docs/walkthrough/media/04-conflicting-instructions.gif",
      limitation: process.env.WALKTHROUGH_CONFLICT_BLOCKER ?? "Both conflict sources were not retrieved.",
      notes:
        "Needs_clarification is caused by the missing end date on this fixture. Retrieval does not route to a dedicated conflict-review status.",
    });
    test.skip(true, process.env.WALKTHROUGH_CONFLICT_BLOCKER ?? "Conflict sources not recordable");
  }

  const requesterVideo = path.join(VIDEO_DIR, "requester.webm");
  const session = await openRecordedSession(browser, "requester", requesterVideo);
  try {
    await submitDemoScenario(session.page, "conflicting-instructions");
    await waitForProcessingStatus(session.page, /Odottaa täsmennystä/);
    await expect(session.page.getByTestId("missing-fields")).toContainText("Loppupäivä");
    await expect(session.page.getByTestId("rule-violations")).toContainText(
      "Määräaikainen vaatii loppupäivän",
    );
    const cardA = session.page.getByTestId(`source-card-${CONFLICT_DOC_A}`);
    const cardB = session.page.getByTestId(`source-card-${CONFLICT_DOC_B}`);
    await expect(cardA).toBeVisible();
    await expect(cardB).toBeVisible();

    await session.page.evaluate(() => window.scrollTo(0, 0));
    await expectEvidenceInViewport(session.page, session.page.getByTestId("processing-status"), 24);
    await holdForReading(session.page, 1_800);

    await revealInViewport(cardA);
    await expect(cardA).toContainText("Ristiriita A");
    await expect(cardA).toContainText("SYN-OHJE-RISTIRIITA-A-01-v1");
    await expectEvidenceInViewport(session.page, cardA, 140);
    await holdForReading(session.page, 2_800);

    await revealInViewport(cardB);
    await expect(cardB).toContainText("Ristiriita B");
    await expect(cardB).toContainText("SYN-OHJE-RISTIRIITA-B-01-v1");
    await expectEvidenceInViewport(session.page, cardB, 140);
    await holdForReading(session.page, 2_800);
  } finally {
    await session.finalize();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "conflicting-instructions",
    assertions: [
      "Status is needs_clarification because end_date is missing",
      `Both ${CONFLICT_DOC_A} and ${CONFLICT_DOC_B} were scrolled into the recorded viewport`,
      `Retrieval used RETRIEVAL_TOP_K=${retrievalTopK}`,
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo],
    planned_gif: "docs/walkthrough/media/04-conflicting-instructions.gif",
    limitation:
      retrievalTopK === "4"
        ? "RETRIEVAL_TOP_K=4 was sufficient for both conflict documents in this recapture."
        : `This recapture API used RETRIEVAL_TOP_K=${retrievalTopK} because both sources were not present at the default 4. The override applied to this recording stack (scenario 04), not as a product default.`,
    notes:
      "Displayed clarification is caused by the missing end date (temporary_requires_end_date). Retrieved instructions are evidence only; there is no automatic conflict-detection status or routing to a manual-review queue.",
  });
});
