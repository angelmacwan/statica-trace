import { test, expect } from "@playwright/test";

test.describe("Replay Panel Flow", () => {
  test.beforeEach(async ({ context }) => {
    // Inject API key into localStorage to skip onboarding
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "mocked_key");
      window.localStorage.setItem("statica_project_name", "test-project");
    });
  });

  test("opens replay panel, edits fields, and verifies output diff", async ({ page }) => {
    const mockTraces = [
      {
        trace_id: "trace-1",
        source: "openai",
        status: "success",
        started_at: "2026-07-10T12:00:00.000Z",
        ended_at: "2026-07-10T12:00:02.500Z",
        duration_ms: 2500,
      },
    ];

    const mockTraceDetail = {
      trace_id: "trace-1",
      source: "openai",
      status: "success",
      started_at: "2026-07-10T12:00:00.000Z",
      ended_at: "2026-07-10T12:00:02.500Z",
      spans: [
        {
          span_id: "span-llm",
          type: "llm_call",
          name: "chat_completion",
          started_at: "2026-07-10T12:00:00.500Z",
          ended_at: "2026-07-10T12:00:02.000Z",
          input: {
            model: "gpt-4o",
            messages: [
              { role: "system", content: "You are a helpful assistant." },
              { role: "user", content: "Say hello!" },
            ],
            params: { temperature: 0.7, max_tokens: 150 },
          },
          output: { content: "Hello! How can I help you today?" },
        },
      ],
    };

    const mockReplayResponse = {
      replay_id: "replay-555",
      trace_id: "trace-1",
      span_id: "span-llm",
      original_output: { content: "Hello! How can I help you today?" },
      replayed_output: { content: "Hi! How can I assist you today?" },
    };

    // Route requests to backend mock data
    await page.route("**/v1/projects/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "proj-1", name: "test-project", created_at: "2026-07-10T12:00:00Z" }),
      });
    });

    await page.route(/\/v1\/traces(\?|$)/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: mockTraces, total: 1, limit: 50, offset: 0 }),
      });
    });

    await page.route(/\/v1\/traces\/[^?]+/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockTraceDetail),
      });
    });

    await page.route("**/v1/replay", async (route) => {
      const requestHeaders = route.request().headers();
      // Assert header was passed
      expect(requestHeaders["x-provider-api-key"]).toBe("my-secret-provider-key");

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockReplayResponse),
      });
    });

    // 1. Visit page and open detail
    await page.goto("/");
    await page.getByText("openai").click();

    // 2. Expand the llm_call span
    await page.getByText("chat_completion").click();

    // 3. Click Replay Debugger button
    await page.getByRole("button", { name: "Replay Debugger" }).click();

    // Verify Replay Panel slides in
    await expect(page.getByTestId("replay-panel")).toBeVisible();

    // 4. Fill in API key
    await page.getByTestId("provider-key-input").fill("my-secret-provider-key");

    // Edit the system prompt
    const systemPromptTextarea = page.getByTestId("message-input-0");
    await expect(systemPromptTextarea).toHaveValue("You are a helpful assistant.");
    await systemPromptTextarea.fill("You are a smart assistant.");

    // 5. Submit replay
    await page.getByTestId("replay-submit-btn").click();

    // 6. Verify diff view renders and contains correct data
    await expect(page.getByTestId("diff-view")).toBeVisible();
    await expect(page.getByText("Original Output")).toBeVisible();
    await expect(page.getByText("Replayed Output (Diffed)")).toBeVisible();

    // Verify word diff content
    await expect(page.getByTestId("diff-view").getByText("assist")).toBeVisible();
  });
});
