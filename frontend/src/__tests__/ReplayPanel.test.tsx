import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ReplayPanel } from "../components/ReplayPanel";

describe("ReplayPanel Component", () => {
  const mockSpan = {
    span_id: "span-123",
    name: "chat_completion",
    type: "llm_call" as const,
    started_at: "2026-07-10T12:00:00Z",
    ended_at: "2026-07-10T12:00:02Z",
    input: {
      model: "gpt-4o-mini",
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Say hello!" },
      ],
      params: {
        temperature: 0.5,
        max_tokens: 150,
      },
    },
    output: {
      content: "Hello! How can I help you?",
    },
  };

  const mockClose = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    mockClose.mockClear();
  });

  it("renders with fields pre-populated from the span's input data", () => {
    render(<ReplayPanel traceId="trace-123" span={mockSpan} onClose={mockClose} />);

    expect(screen.getByDisplayValue("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.5")).toBeInTheDocument();
    expect(screen.getByDisplayValue("150")).toBeInTheDocument();
    expect(screen.getByDisplayValue("You are a helpful assistant.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Say hello!")).toBeInTheDocument();
  });

  it("updates message contents in local state when textareas are edited", () => {
    render(<ReplayPanel traceId="trace-123" span={mockSpan} onClose={mockClose} />);

    const systemPromptTextarea = screen.getByTestId("message-input-0");
    fireEvent.change(systemPromptTextarea, { target: { value: "You are a mean robot." } });
    expect(systemPromptTextarea).toHaveValue("You are a mean robot.");

    const userTextarea = screen.getByTestId("message-input-1");
    fireEvent.change(userTextarea, { target: { value: "Tell me a joke." } });
    expect(userTextarea).toHaveValue("Tell me a joke.");
  });

  it("disables 'Run Replay' button and shows loading state while a replay is in progress", async () => {
    // Return a promise that doesn't resolve immediately
    global.fetch = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(new Response()), 100))
    );

    render(<ReplayPanel traceId="trace-123" span={mockSpan} onClose={mockClose} />);

    // API key input is required to enable or submit
    const apiKeyInput = screen.getByTestId("provider-key-input");
    fireEvent.change(apiKeyInput, { target: { value: "test-key-123" } });

    const submitBtn = screen.getByTestId("replay-submit-btn");
    fireEvent.click(submitBtn);

    // Should immediately show loading text and be disabled
    expect(screen.getByText("Executing Replay...")).toBeInTheDocument();
    expect(submitBtn).toBeDisabled();
  });

  it("renders the diff view with both original and replayed outputs on successful replay", async () => {
    const mockReplayResponse = {
      replay_id: "replay-999",
      trace_id: "trace-123",
      span_id: "span-123",
      original_output: { content: "Hello! How can I help you?" },
      replayed_output: { content: "Hi! How can I assist you today?" },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockReplayResponse,
    } as any);

    render(<ReplayPanel traceId="trace-123" span={mockSpan} onClose={mockClose} />);

    // Put in API key
    const apiKeyInput = screen.getByTestId("provider-key-input");
    fireEvent.change(apiKeyInput, { target: { value: "test-key-123" } });

    const submitBtn = screen.getByTestId("replay-submit-btn");
    fireEvent.click(submitBtn);

    // Wait for diff view to render
    await waitFor(() => {
      expect(screen.getByTestId("diff-view")).toBeInTheDocument();
    });

    // Check headers
    expect(screen.getByText("Original Output")).toBeInTheDocument();
    expect(screen.getByText("Replayed Output (Diffed)")).toBeInTheDocument();

    // Check content and diff highlights
    expect(screen.getByText("Hello! How can I help you?")).toBeInTheDocument();
    // Words added or removed should be present in the document
    expect(screen.getByText("assist")).toBeInTheDocument();
    expect(screen.getByText("today?")).toBeInTheDocument();

    // Assert fetch was called with the provider key in header
    const fetchCall = vi.mocked(global.fetch).mock.calls[0];
    expect(fetchCall[0]).toBe("http://localhost:8000/v1/replay");
    const fetchOptions = fetchCall[1] as RequestInit;
    const requestHeaders = fetchOptions.headers as Headers;
    expect(requestHeaders.get("X-Provider-Api-Key")).toBe("test-key-123");
  });

  it("renders an inline error message on API failure", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "OpenAI API key was rejected" }),
    } as any);

    render(<ReplayPanel traceId="trace-123" span={mockSpan} onClose={mockClose} />);

    // Put in API key
    const apiKeyInput = screen.getByTestId("provider-key-input");
    fireEvent.change(apiKeyInput, { target: { value: "bad-key" } });

    const submitBtn = screen.getByTestId("replay-submit-btn");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("OpenAI API key was rejected")).toBeInTheDocument();
    });
  });
});
