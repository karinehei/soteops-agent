import { expect, test as setup } from "@playwright/test";
import { mkdirSync } from "node:fs";

import { DEMO_USERS } from "../src/lib/demo-scenarios";
import { STORAGE_DIR, expectBanner, storageStatePath } from "./helpers";

setup.describe.configure({ mode: "serial" });

for (const role of ["requester", "reviewer"] as const) {
  setup(`authenticate ${role} without recording`, async ({ page }) => {
    mkdirSync(STORAGE_DIR, { recursive: true });
    const user = DEMO_USERS[role];
    await page.goto("/login");
    await expectBanner(page);
    await page.locator("#email").fill(user.email);
    await page.locator("#password").fill(user.password);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("current-user")).toContainText(user.displayName);
    await page.context().storageState({ path: storageStatePath(role) });
  });
}
