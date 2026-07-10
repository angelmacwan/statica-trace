import { test, expect } from "@playwright/test";

test.describe("Frontend Polish (Sprint 5.1)", () => {

  test("failed GET /v1/traces shows error banner with retry button", async ({ page, context }) => {
    // Inject API key into localStorage to skip initial onboarding
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "mocked_key");
      window.localStorage.setItem("statica_project_name", "test-project");
    });

    let failRequest = true;

    await page.route(/\/v1\/traces(\?|$)/, async (route) => {
      if (failRequest) {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Database connection failed" }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }),
        });
      }
    });

    await page.goto("/");

    // Error banner should show up
    const errorBanner = page.getByTestId("error-banner");
    await expect(errorBanner).toBeVisible();
    await expect(errorBanner).toContainText("Database connection failed");

    const retryBtn = page.getByTestId("retry-btn");
    await expect(retryBtn).toBeVisible();

    // Make next request succeed
    failRequest = false;
    await retryBtn.click();

    // Error banner should disappear and empty state (or trace list) should show
    await expect(errorBanner).not.toBeVisible();
    await expect(page.getByText("No traces yet")).toBeVisible();
  });

  test("failed GET /v1/traces/{id} with 404 status shows Trace not found", async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "mocked_key");
      window.localStorage.setItem("statica_project_name", "test-project");
    });

    await page.route(/\/v1\/traces\/trace-123/, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Trace not found." }),
      });
    });

    // Go directly to the trace page
    await page.goto("/traces/trace-123");

    await expect(page.getByText("Trace not found")).toBeVisible();
    await expect(page.getByRole("button", { name: "Back to List" })).toBeVisible();
  });

  test("401 unauthorized on request redirects to login/API key page", async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "expired_key");
      window.localStorage.setItem("statica_project_name", "test-project");
    });

    await page.route(/\/v1\/traces(\?|$)/, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid token" }),
      });
    });

    await page.goto("/");

    // Should detect 401 and redirect to login page (Onboarding component in default state)
    await expect(page.getByRole("heading", { name: "Statica Trace" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Project" }).first()).toBeVisible();
  });

  test("Empty states: trace detail with no spans shows upgraded empty state with actions", async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "mocked_key");
      window.localStorage.setItem("statica_project_name", "test-project");
    });

    await page.route(/\/v1\/traces\/trace-empty/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          trace_id: "trace-empty",
          source: "langchain",
          status: "success",
          started_at: "2026-07-10T12:00:00Z",
          ended_at: "2026-07-10T12:00:05Z",
          spans: [],
        }),
      });
    });

    await page.goto("/traces/trace-empty");

    const emptySpans = page.getByTestId("empty-spans");
    await expect(emptySpans).toBeVisible();
    await expect(emptySpans).toContainText("No spans captured");
    await expect(emptySpans.getByRole("button", { name: "Back to Traces" })).toBeVisible();
    await expect(page.getByTestId("refresh-btn")).toBeVisible();
  });

  test("Onboarding direct navigation with API key displays integration guide", async ({ page, context }) => {
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "existing_key_123");
      window.localStorage.setItem("statica_project_name", "My Production Agent");
    });

    await page.route("**/v1/projects/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "proj-1", name: "My Production Agent" }),
      });
    });

    await page.goto("/onboarding");

    // Title should be custom for existing configuration
    await expect(page.getByRole("heading", { name: "My Production Agent Setup" })).toBeVisible();
    await expect(page.getByText("Project Configuration")).toBeVisible();
    await expect(page.getByText("existing_key_123")).toBeVisible();

    const dashboardBtn = page.getByRole("button", { name: "Go to Dashboard" });
    await expect(dashboardBtn).toBeVisible();

    // Verify navigating to dashboard leads back to traces
    await page.route(/\/v1\/traces(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0 }),
      });
    });

    await dashboardBtn.click();
    await expect(page.url()).toContain("/traces");
  });
});
