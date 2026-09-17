import {
  expect,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

import { DEMO_USERS } from "../src/lib/demo-scenarios";

export const VIEWPORT = { width: 1440, height: 900 } as const;
export const READING_PAUSE_MS = 1_400;

export const ARTIFACT_ROOT = process.env.WALKTHROUGH_ARTIFACT_DIR
  ? path.resolve(process.env.WALKTHROUGH_ARTIFACT_DIR)
  : path.resolve(__dirname, "..", "..", "artifacts", "walkthrough");

export const STORAGE_DIR = path.join(ARTIFACT_ROOT, "storage");

export const API_BASE = process.env.WALKTHROUGH_API_BASE_URL ?? "http://127.0.0.1:8010";
export const MOCK_BASE = process.env.WALKTHROUGH_MOCK_BASE_URL ?? "http://127.0.0.1:8011";

export const CONFLICT_DOC_A = "SYN-OHJE-RISTIRIITA-A-01-v1";
export const CONFLICT_DOC_B = "SYN-OHJE-RISTIRIITA-B-01-v1";

export function storageStatePath(role: "requester" | "reviewer"): string {
  return path.join(STORAGE_DIR, `${role}.json`);
}

export async function holdForReading(page: Page, ms = READING_PAUSE_MS): Promise<void> {
  await page.waitForTimeout(ms);
}

export async function revealInViewport(locator: Locator): Promise<void> {
  const target = locator.first();
  await expect(target).toBeVisible();
  await target.evaluate((node: HTMLElement) => {
    node.scrollIntoView({ block: "center", inline: "nearest" });
  });
}

export async function expectEvidenceInViewport(
  page: Page,
  locator: Locator,
  minVisiblePx = 72,
): Promise<void> {
  const box = await locator.first().boundingBox();
  const viewport = page.viewportSize();
  if (!box) {
    throw new Error("Evidence element has no bounding box");
  }
  if (!viewport) {
    throw new Error("Page has no viewport size");
  }
  expect(box.height).toBeGreaterThan(0);
  expect(box.y + minVisiblePx).toBeLessThanOrEqual(viewport.height);
  expect(box.y + box.height).toBeGreaterThan(0);
}

export async function expectBanner(page: Page): Promise<void> {
  await expect(page.getByRole("note")).toContainText("Synteettinen demoaineisto");
}

export async function waitForProcessingStatus(page: Page, pattern: RegExp): Promise<void> {
  await expect(page.getByTestId("processing-status")).toContainText(pattern, { timeout: 60_000 });
}

export function requestIdFromUrl(url: string): string {
  const id = url.split("/").pop();
  if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
    throw new Error(`Could not parse request id from ${url}`);
  }
  return id;
}

export interface RecordedSession {
  context: BrowserContext;
  page: Page;
  finalize: () => Promise<string>;
}

export async function openRecordedSession(
  browser: Browser,
  role: "requester" | "reviewer",
  videoPath: string,
): Promise<RecordedSession> {
  mkdirSync(path.dirname(videoPath), { recursive: true });
  const tmpDir = `${videoPath}.tmp`;
  rmSync(tmpDir, { recursive: true, force: true });
  mkdirSync(tmpDir, { recursive: true });
  const context = await browser.newContext({
    storageState: storageStatePath(role),
    viewport: VIEWPORT,
    recordVideo: { dir: tmpDir, size: VIEWPORT },
  });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await expectBanner(page);
    await expect(page.getByTestId("current-user")).toContainText(DEMO_USERS[role].displayName);
    return {
      context,
      page,
      finalize: async () => {
        const video = page.video();
        await page.close();
        await context.close();
        if (!video) {
          throw new Error(`No video recorded for ${role} at ${videoPath}`);
        }
        await video.saveAs(videoPath);
        rmSync(tmpDir, { recursive: true, force: true });
        return videoPath;
      },
    };
  } catch (error) {
    await context.close();
    rmSync(tmpDir, { recursive: true, force: true });
    throw error;
  }
}

export async function submitDemoScenario(page: Page, scenarioId: string): Promise<string> {
  await page.goto(`/requests/new?scenario=${scenarioId}`);
  await expectBanner(page);
  await expect(page.getByTestId("request-form")).toBeVisible();
  await page.getByTestId("request-form").getByRole("button", { name: "Lähetä valmisteltavaksi" }).click();
  await expect(page).toHaveURL(/\/requests\/[0-9a-f-]+$/);
  return requestIdFromUrl(page.url());
}

export interface ScenarioResult {
  id: string;
  fixture: string;
  assertions: string[];
  assertions_passed: boolean;
  outcome: "passed" | "failed" | "blocked" | "skipped";
  video_segments: string[];
  planned_gif: string;
  limitation: string;
  notes: string;
}

export function writeScenarioResult(result: ScenarioResult): void {
  const dir = path.join(ARTIFACT_ROOT, "results");
  mkdirSync(dir, { recursive: true });
  writeFileSync(path.join(dir, `${result.id}.json`), `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

export async function apiForRole(
  playwright: { request: { newContext: (options?: Record<string, unknown>) => Promise<APIRequestContext> } },
  role: "requester" | "reviewer",
): Promise<APIRequestContext> {
  return playwright.request.newContext({
    baseURL: API_BASE,
    storageState: storageStatePath(role),
  });
}

export async function csrfHeaders(api: APIRequestContext): Promise<Record<string, string>> {
  const response = await api.get("/auth/csrf");
  if (!response.ok()) {
    throw new Error(`CSRF fetch failed: ${response.status()}`);
  }
  const body = (await response.json()) as { csrf_token: string };
  return { "X-CSRF-Token": body.csrf_token };
}

export async function getRequest(api: APIRequestContext, requestId: string) {
  const response = await api.get(`/requests/${requestId}`);
  if (!response.ok()) {
    throw new Error(`GET /requests/${requestId} failed: ${response.status()}`);
  }
  return response.json();
}

export async function mockRecords(): Promise<{
  count: number;
  stores_accounts: boolean;
  records: Array<{ record_id: string; idempotency_key: string }>;
}> {
  const response = await fetch(`${MOCK_BASE}/records`);
  if (!response.ok) {
    throw new Error(`GET ${MOCK_BASE}/records failed: ${response.status}`);
  }
  return response.json() as Promise<{
    count: number;
    stores_accounts: boolean;
    records: Array<{ record_id: string; idempotency_key: string }>;
  }>;
}

export async function mockLookup(idempotencyKey: string): Promise<{
  record_id: string;
  stores_accounts: boolean;
}> {
  const response = await fetch(
    `${MOCK_BASE}/requests?idempotency_key=${encodeURIComponent(idempotencyKey)}`,
  );
  if (!response.ok) {
    throw new Error(`Mock lookup failed: ${response.status}`);
  }
  return response.json() as Promise<{ record_id: string; stores_accounts: boolean }>;
}
