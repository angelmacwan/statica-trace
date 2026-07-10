import { test, expect } from "@playwright/test";

test.describe("Trace Navigation Flow", () => {
  test.beforeEach(async ({ context }) => {
    // Inject API key into localStorage to skip onboarding
    await context.addInitScript(() => {
      window.localStorage.setItem("statica_api_key", "mocked_key");
      window.localStorage.setItem("statica_project_name", "test-project");
    });
  });

  test("loads trace list, filters, and inspects trace details", async ({ page }) => {
    const mockTraces = [
      {
        trace_id: "trace-1",
        source: "langchain",
        status: "success",
        started_at: "2026-07-10T12:00:00.000Z",
        ended_at: "2026-07-10T12:00:02.500Z",
        duration_ms: 2500,
      },
      {
        trace_id: "trace-2",
        source: "openai",
        status: "error",
        started_at: "2026-07-10T12:05:00.000Z",
        ended_at: "2026-07-10T12:05:01.000Z",
        duration_ms: 1000,
      },
    ];

    const mockTraceDetail = {
      trace_id: "trace-1",
      source: "langchain",
      status: "success",
      started_at: "2026-07-10T12:00:00.000Z",
      ended_at: "2026-07-10T12:00:02.500Z",
      spans: [
        {
          span_id: "span-root",
          type: "agent_step",
          name: "agent_router",
          started_at: "2026-07-10T12:00:00.000Z",
          ended_at: "2026-07-10T12:00:02.500Z",
          input: { query: "Tell me a joke." },
          output: { result: "Why did the robot cross the road? To debug the other side." },
        },
        {
          span_id: "span-child",
          parent_span_id: "span-root",
          type: "llm_call",
          name: "chat_completion",
          started_at: "2026-07-10T12:00:00.500Z",
          ended_at: "2026-07-10T12:00:02.000Z",
          input: {
            model: "gpt-4o",
            messages: [{ role: "user", content: "Tell me a joke." }],
            params: { temperature: 0.7 },
          },
          output: { content: "Why did the robot cross the road? To debug the other side." },
        },
      ],
    };

    // Route requests to backend mock data
    // Listen to browser console logs
    page.on("console", (msg) => console.log(`BROWSER LOG: ${msg.text()}`));

    await page.route("**/v1/projects/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "proj-1", name: "test-project", created_at: "2026-07-10T12:00:00Z" }),
      });
    });

    await page.route(/\/v1\/traces(\?|$)/, async (route) => {
      const url = new URL(route.request().url());
      const statusParam = url.searchParams.get("status");
      console.log(`Intercepted URL: ${route.request().url()}, statusParam: ${statusParam}`);
      if (statusParam === "error") {
        console.log("Fulfilling with error traces only");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [mockTraces[1]], total: 1, limit: 50, offset: 0 }),
        });
      } else {
        console.log("Fulfilling with all traces");
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: mockTraces, total: 2, limit: 50, offset: 0 }),
        });
      }
    });

    await page.route(/\/v1\/traces\/[^?]+/, async (route) => {
      console.log(`Intercepted Detail URL: ${route.request().url()}`);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockTraceDetail),
      });
    });

    // 1. Visit traces page (loads automatically since API key is set)
    await page.goto("/");

    // Verify trace rows loaded
    await expect(page.getByText("langchain")).toBeVisible();
    await expect(page.getByText("openai")).toBeVisible();

    // 2. Click "Errors" filter
    await page.getByRole("button", { name: "Errors" }).click();
    // Verify only openai is visible, langchain is filtered out
    await expect(page.getByText("openai")).toBeVisible();
    await expect(page.getByText("langchain")).not.toBeVisible();

    // 3. Click "All Traces" filter
    await page.getByRole("button", { name: "All Traces" }).click();
    await expect(page.getByText("langchain")).toBeVisible();

    // 4. Click trace row to navigate
    await page.getByText("langchain").click();

    // Verify we navigated to trace detail and the spans are rendered
    await expect(page.getByRole("heading", { name: "Trace Timeline" })).toBeVisible();
    await expect(page.getByText("agent_router")).toBeVisible();
    await expect(page.getByText("chat_completion")).toBeVisible();

    // 5. Expand span details
    await page.getByText("agent_router").click();
    // Verify inline input details are visible
    await expect(page.getByText("Tell me a joke.")).toBeVisible();
  });
});
