import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  CONFLICT_DOC_A,
  CONFLICT_DOC_B,
  holdForReading,
  openRecordedSession,
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
        "Both conflict instruction documents must appear in source_references",
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
    await expect(session.page.getByTestId(`source-card-${CONFLICT_DOC_A}`)).toBeVisible();
    await expect(session.page.getByTestId(`source-card-${CONFLICT_DOC_B}`)).toBeVisible();
    await session.page.getByTestId("source-references").scrollIntoViewIfNeeded();
    await holdForReading(session.page, 2_000);
  } finally {
    await session.finalize();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "conflicting-instructions",
    assertions: [
      "Status is needs_clarification because end_date is missing",
      `Both ${CONFLICT_DOC_A} and ${CONFLICT_DOC_B} are visible`,
      `Retrieval used RETRIEVAL_TOP_K=${retrievalTopK}`,
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo],
    planned_gif: "docs/walkthrough/media/04-conflicting-instructions.gif",
    limitation:
      retrievalTopK === "4"
        ? ""
        : `Recording stack used RETRIEVAL_TOP_K=${retrievalTopK} because both sources were not present at the default 4.`,
    notes:
      "Displayed clarification is caused by the missing end date (temporary_requires_end_date). Retrieved instructions are evidence only; there is no automatic conflict-detection status or routing to a manual-review queue.",
  });
});
