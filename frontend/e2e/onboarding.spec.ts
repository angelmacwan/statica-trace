import { test, expect } from "@playwright/test";

test.describe("Onboarding Flow", () => {
  test("creates a project and views integration snippets", async ({ page }) => {
    // Intercept project creation API
    await page.route("**/v1/projects", async (route) => {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "proj-abc",
          name: "customer-service",
          api_key: "statica_key_123456789",
          created_at: "2026-07-10T12:00:00Z",
        }),
      });
    });

    // 1. Navigate to home page
    await page.goto("/");

    // Assert Onboarding title is visible
    await expect(page.getByRole("heading", { name: "Statica Trace" })).toBeVisible();

    // 2. Fill in project name and submit
    const nameInput = page.getByPlaceholder("e.g. customer-service-agent");
    await nameInput.fill("customer-service");
    await page.locator("form").getByRole("button", { name: "Create Project" }).click();

    // 3. Verify success view
    await expect(page.getByRole("heading", { name: "Welcome to customer-service" })).toBeVisible();

    // Verify key masking by checking if first and last 4 characters are present
    const keyDisplay = page.getByTestId("api-key-display");
    await expect(keyDisplay).toBeVisible();
    await expect(keyDisplay).toContainText("stat");

    // Verify default LangChain tab content
    const codeBlock = page.locator("pre");
    await expect(codeBlock).toContainText("AgentReplayCallbackHandler");
    await expect(codeBlock).toContainText("statica_key_123456789");

    // 4. Click OpenAI tab and verify it updates
    await page.getByRole("button", { name: "OpenAI" }).click();
    await expect(codeBlock).toContainText("openai_wrapper import wrap");

    // 5. Verify Copy Snippet button is present
    const copyBtn = page.getByRole("button", { name: "Copy Snippet" });
    await expect(copyBtn).toBeVisible();
  });
});
