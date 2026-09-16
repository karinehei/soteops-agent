import { expect, test } from "@playwright/test";

import { login, newBrowserPage, waitForProcessingStatus } from "./helpers";

test("stale approve after requester edit is rejected in UI", async ({ browser }) => {
  const requesterPage = await newBrowserPage(browser);
  await login(requesterPage, "requester");
  await requesterPage.goto("/requests/new?scenario=approval-bypass");
  await requesterPage.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
  await waitForProcessingStatus(requesterPage, /Odottaa tarkastusta|Valmistellaan/);
  const requestId = requesterPage.url().split("/").pop()!;

  const reviewerPage = await newBrowserPage(browser);
  await login(reviewerPage, "reviewer");
  await reviewerPage.goto(`/review/${requestId}`);
  await waitForProcessingStatus(reviewerPage, /Odottaa tarkastusta/);
  await reviewerPage.getByRole("button", { name: "Aloita tarkastus" }).click();

  await requesterPage.goto(`/requests/${requestId}`);
  await requesterPage.getByRole("button", { name: "Muokkaa ja täsmennä" }).click();
  await requesterPage
    .getByLabel("Alkuperäinen teksti")
    .fill(
      "Päivitetty synteettinen teksti EMP-6006 demo-hr-testi lukuoikeus vakituinen demo-osasto 2026-10-01.",
    );
  await requesterPage.getByRole("button", { name: "Tallenna muutokset" }).click();
  await expect(requesterPage.getByTestId("invalidation-notice")).toBeVisible();

  await reviewerPage.getByTestId("approve-button").click();
  await expect(reviewerPage.getByTestId("review-error")).toContainText(/Stale|vanhentunut|409|proposal|revision/i);
});
