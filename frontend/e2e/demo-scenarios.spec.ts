import { expect, test } from "@playwright/test";

import { DEMO_SCENARIOS } from "../src/lib/demo-scenarios";
import { login, waitForProcessingStatus } from "./helpers";

for (const scenario of DEMO_SCENARIOS.filter((item) => item.id !== "approval-bypass")) {
  test(`demo scenario: ${scenario.id}`, async ({ page }) => {
    await login(page, "requester");
    await page.goto(`/requests/new?scenario=${scenario.id}`);
    await page.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
    await expect(page.getByTestId("processing-status")).toBeVisible({ timeout: 60_000 });

    if (scenario.expectedPhase === "needs_clarification") {
      await waitForProcessingStatus(page, /Odottaa täsmennystä/);
      await expect(page.getByTestId("approval-eligibility")).toHaveCount(0);
    } else {
      await waitForProcessingStatus(page, /Odottaa tarkastusta|Valmistellaan/);
    }
  });
}

test("downstream lost-response demo reconciles after forward", async ({ page, browser }) => {
  await login(page, "requester");
  await page.goto("/requests/new?scenario=downstream-timeout");
  await page.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
  await waitForProcessingStatus(page, /Odottaa tarkastusta|Valmistellaan/);
  const requestId = page.url().split("/").pop()!;

  const reviewer = await browser.newContext();
  const reviewerPage = await reviewer.newPage();
  await login(reviewerPage, "reviewer");
  await reviewerPage.goto(`/review/${requestId}`);
  await reviewerPage.getByRole("button", { name: "Aloita tarkastus" }).click();
  await reviewerPage.getByTestId("approve-button").click();
  await expect(reviewerPage.getByTestId("forward-button")).toBeEnabled();
  await reviewerPage.selectOption("#demo-fault", "lost-response");
  await reviewerPage.getByTestId("forward-button").click();
  await expect(reviewerPage.getByTestId("submission-panel")).toContainText(/Mock-tietue|Vastaanotettu/, {
    timeout: 30_000,
  });
  await reviewer.close();
});
