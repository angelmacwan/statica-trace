/**
 * smoke.spec.ts — Playwright E2E smoke test (backlog item 0.2.2)
 *
 * Acceptance criteria:
 * - A trivial smoke test exists: navigates to `/` and asserts the page
 *   title is correct.
 */
import { test, expect } from "@playwright/test";

test("home page has correct title", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Statica Trace/i);
});

test("home page renders the h1 heading", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Statica Trace"
  );
});
