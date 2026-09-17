import { expect, test } from "@playwright/test";

import { login, waitForProcessingStatus } from "./helpers";

test("requester can correct missing end date and become eligible for review", async ({ page }) => {
  await login(page, "requester");
  await page.goto("/requests/new?scenario=temporary-missing-end");
  await page.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
  await waitForProcessingStatus(page, /Odottaa täsmennystä/);
  await expect(page.getByTestId("missing-fields")).toContainText("Loppupäivä");
  await expect(page.getByTestId("approval-eligibility")).toHaveCount(0);

  await page.getByRole("button", { name: "Muokkaa ja täsmennä" }).click();
  await page.getByLabel("Loppupäivä").fill("2026-12-31");
  await page.getByRole("button", { name: "Tallenna muutokset" }).click();
  await waitForProcessingStatus(page, /Odottaa tarkastusta/);
  await expect(page.getByTestId("proposal-panel")).toContainText(
    "Ei puuttuvia kenttiä eikä estäviä sääntöhavaintoja",
  );
});
