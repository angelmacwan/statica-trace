import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TraceDetail } from "../components/TraceDetail";

describe("TraceDetail Component", () => {
  const mockTraceId = "trace-123";
  const mockBack = vi.fn();
  const mockReplayClick = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    mockBack.mockClear();
    mockReplayClick.mockClear();
  });

  it("renders a loading spinner initially", async () => {
    global.fetch = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(new Response()), 50))
    );

    render(
      <TraceDetail
        traceId={mockTraceId}
        onBack={mockBack}
        onReplayClick={mockReplayClick}
      />
    );

    expect(screen.getByText("Loading trace details...")).toBeInTheDocument();
  });

  it("renders empty state when there are no spans", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        trace_id: mockTraceId,
        source: "langchain",
        status: "success",
        started_at: "2026-07-10T12:00:00Z",
        ended_at: "2026-07-10T12:00:05Z",
        spans: [],
      }),
    } as any);

    render(
      <TraceDetail
        traceId={mockTraceId}
        onBack={mockBack}
        onReplayClick={mockReplayClick}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("No spans captured")).toBeInTheDocument();
    });

    expect(screen.getByText(/This trace is empty and doesn't contain any spans/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /back to traces/i }).length).toBe(2);
    expect(screen.getByRole("button", { name: /refresh details/i })).toBeInTheDocument();
  });

  it("renders trace not found error when API returns 404", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "Trace not found." }),
    } as any);

    render(
      <TraceDetail
        traceId={mockTraceId}
        onBack={mockBack}
        onReplayClick={mockReplayClick}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Trace not found")).toBeInTheDocument();
    });
  });

  it("renders generic error message when API returns 500", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ detail: "Database connection failed" }),
    } as any);

    render(
      <TraceDetail
        traceId={mockTraceId}
        onBack={mockBack}
        onReplayClick={mockReplayClick}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Database connection failed")).toBeInTheDocument();
    });
  });
});
