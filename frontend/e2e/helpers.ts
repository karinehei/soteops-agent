import { expect, type Browser, type Page } from "@playwright/test";

import { DEMO_SCENARIOS, DEMO_USERS } from "../src/lib/demo-scenarios";

export async function login(page: Page, role: keyof typeof DEMO_USERS): Promise<void> {
  const user = DEMO_USERS[role];
  await page.goto("/login");
  await page.getByLabel("Sähköposti").fill(user.email);
  await page.getByLabel("Salasana").fill(user.password);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("current-user")).toContainText(user.displayName);
}

export async function newBrowserPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext();
  return context.newPage();
}

export function completeScenarioPayload() {
  return DEMO_SCENARIOS.find((item) => item.id === "complete-permanent")!.payload;
}

export async function waitForProcessingStatus(page: Page, pattern: RegExp): Promise<void> {
  await expect(page.getByTestId("processing-status")).toContainText(pattern, {
    timeout: 60_000,
  });
}
