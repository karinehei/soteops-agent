import { expect, test } from "@playwright/test";
import path from "node:path";

import {
  ARTIFACT_ROOT,
  expectEvidenceInViewport,
  holdForReading,
  openRecordedSession,
  revealInViewport,
  submitDemoScenario,
  waitForProcessingStatus,
  writeScenarioResult,
} from "./helpers";

const SCENARIO_ID = "02-missing-end-date";
const VIDEO_DIR = path.join(ARTIFACT_ROOT, SCENARIO_ID);
const retrievalTopK = process.env.WALKTHROUGH_RETRIEVAL_TOP_K ?? "4";

test("02 missing end date: clarification, correction, eligible after reprepare", async ({
  browser,
}) => {
  const requesterVideo = path.join(VIDEO_DIR, "requester.webm");
  const session = await openRecordedSession(browser, "requester", requesterVideo);
  try {
    await submitDemoScenario(session.page, "temporary-missing-end");
    await waitForProcessingStatus(session.page, /Odottaa täsmennystä/);
    await expect(session.page.getByTestId("missing-fields")).toContainText("Loppupäivä");
    await expect(session.page.getByTestId("rule-violations")).toContainText(
      "Määräaikainen vaatii loppupäivän",
    );
    await expect(session.page.getByTestId("approval-eligibility")).toHaveCount(0);
    await expect(session.page.getByTestId("approve-button")).toHaveCount(0);
    await session.page.evaluate(() => window.scrollTo(0, 0));
    await expectEvidenceInViewport(session.page, session.page.getByTestId("processing-status"), 24);
    await holdForReading(session.page, 1_800);

    await session.page.getByRole("button", { name: "Muokkaa ja täsmennä" }).click();
    await session.page.getByLabel("Loppupäivä").fill("2026-12-31");
    await session.page.getByRole("button", { name: "Tallenna muutokset" }).click();
    await waitForProcessingStatus(session.page, /Odottaa tarkastusta/);
    await expect(session.page.getByTestId("missing-fields")).toHaveCount(0);
    await expect(session.page.getByTestId("rule-violations")).toHaveCount(0);
    await expect(session.page.getByTestId("proposal-panel")).toContainText(
      "Ei puuttuvia kenttiä eikä estäviä sääntöhavaintoja",
    );
    await session.page.evaluate(() => window.scrollTo(0, 0));
    await expect(session.page.getByTestId("processing-status")).toContainText(/Odottaa tarkastusta/);
    await expectEvidenceInViewport(session.page, session.page.getByTestId("processing-status"), 24);
    await holdForReading(session.page, 2_000);
    await revealInViewport(
      session.page.getByRole("heading", { name: "Puuttuvat tiedot ja sääntöhavainnot" }),
    );
    await expect(session.page.getByTestId("proposal-panel")).toContainText("2026-12-31");
    await expect(session.page.getByTestId("proposal-panel")).toContainText(
      "Ei puuttuvia kenttiä eikä estäviä sääntöhavaintoja",
    );
    await holdForReading(session.page, 2_000);
  } finally {
    await session.finalize();
  }

  writeScenarioResult({
    id: SCENARIO_ID,
    fixture: "temporary-missing-end",
    assertions: [
      "Initial status needs_clarification with missing end_date",
      "Requester saved an end date and preparation ran again",
      "Resulting status is ready_for_review with no blocking findings",
      "Status badge and empty findings were scrolled into the recorded viewport",
    ],
    assertions_passed: true,
    outcome: "passed",
    video_segments: [requesterVideo],
    planned_gif: "docs/walkthrough/media/02-missing-end-date.gif",
    limitation: "",
    notes:
      `Correction uses PATCH + immediate reprepare. No reviewer approve in this clip. ` +
      `This recapture stack used RETRIEVAL_TOP_K=${retrievalTopK}; the scenario does not depend on retrieval top_k.`,
  });
});
