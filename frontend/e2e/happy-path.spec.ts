import { expect, test } from "@playwright/test";

import { completeScenarioPayload, login, newBrowserPage, waitForProcessingStatus } from "./helpers";

test("requester submit → reviewer approve → forward shows mock record", async ({ browser }) => {
  const requesterPage = await newBrowserPage(browser);
  await login(requesterPage, "requester");

  await requesterPage.goto("/requests/new?scenario=complete-permanent");
  await requesterPage.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
  await expect(requesterPage).toHaveURL(/\/requests\/[0-9a-f-]+$/);
  await waitForProcessingStatus(requesterPage, /Odottaa tarkastusta|Valmistellaan/);

  const requestUrl = requesterPage.url();
  const requestId = requestUrl.split("/").pop()!;

  const reviewerPage = await newBrowserPage(browser);
  await login(reviewerPage, "reviewer");
  await reviewerPage.goto(`/review/${requestId}`);
  await waitForProcessingStatus(reviewerPage, /Odottaa tarkastusta|Tarkastuksessa/);

  await reviewerPage.getByRole("button", { name: "Aloita tarkastus" }).click();
  await expect(reviewerPage.getByTestId("approval-eligibility")).toContainText("kelpaa hyväksyntään");
  await reviewerPage.getByTestId("approve-button").click();
  await expect(reviewerPage.getByTestId("processing-status")).toContainText(/Hyväksytty|Odottaa lähetystä/);

  await reviewerPage.getByTestId("forward-button").click();
  await expect(reviewerPage.getByTestId("submission-panel")).toContainText(/Mock-tietue|Vastaanotettu/, {
    timeout: 30_000,
  });
  await expect(reviewerPage.getByTestId("audit-timeline")).toContainText("Hyväksytty");
});

test("requester can create from form fields", async ({ page }) => {
  await login(page, "requester");
  await page.goto("/requests/new");
  const payload = completeScenarioPayload();
  await page.getByLabel("Alkuperäinen teksti").fill(payload.original_text);
  await page.getByLabel("Työntekijätunnus").fill(payload.employee_identifier ?? "");
  await page.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
  await expect(page.getByTestId("proposal-panel")).toBeVisible({ timeout: 60_000 });
});
