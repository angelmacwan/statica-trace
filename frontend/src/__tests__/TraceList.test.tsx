import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TraceList } from "../components/TraceList";

describe("TraceList Component", () => {
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

  const mockSelectTrace = vi.fn();
  const mockGoToOnboarding = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    mockSelectTrace.mockClear();
    mockGoToOnboarding.mockClear();
  });

  it("renders a loading skeleton initially", async () => {
    // Return a promise that doesn't resolve immediately
    global.fetch = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(new Response()), 50))
    );

    render(<TraceList onSelectTrace={mockSelectTrace} onGoToOnboarding={mockGoToOnboarding} />);
    
    // Check that we have animating placeholder rows
    const tbody = document.querySelector("tbody");
    expect(tbody?.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders list items after loading successfully", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: mockTraces, total: 2, limit: 50, offset: 0 }),
    } as any);

    render(<TraceList onSelectTrace={mockSelectTrace} onGoToOnboarding={mockGoToOnboarding} />);

    await waitFor(() => {
      expect(screen.getByText(/langchain/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/openai/i)).toBeInTheDocument();
    expect(screen.getAllByText("Success").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Error").length).toBeGreaterThan(0);
    expect(screen.getByText("2.50s")).toBeInTheDocument();
    expect(screen.getByText("1.00s")).toBeInTheDocument();
  });

  it("renders an error banner when api fetch fails and retries on click", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({ detail: "Database connection failed" }),
    } as any);

    render(<TraceList onSelectTrace={mockSelectTrace} onGoToOnboarding={mockGoToOnboarding} />);

    await waitFor(() => {
      expect(screen.getByText("Database connection failed")).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();

    // Mock successful fetch on retry
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: mockTraces, total: 2, limit: 50, offset: 0 }),
    } as any);

    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText(/langchain/i)).toBeInTheDocument();
    });
  });

  it("renders empty state when there are no traces", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, limit: 50, offset: 0 }),
    } as any);

    render(<TraceList onSelectTrace={mockSelectTrace} onGoToOnboarding={mockGoToOnboarding} />);

    await waitFor(() => {
      expect(screen.getByText("No traces yet")).toBeInTheDocument();
    });

    expect(screen.getByText(/We couldn't find any traces/)).toBeInTheDocument();
    
    const setupBtn = screen.getByRole("button", { name: /view setup instructions/i });
    expect(setupBtn).toBeInTheDocument();
    fireEvent.click(setupBtn);
    expect(mockGoToOnboarding).toHaveBeenCalled();
  });

  it("applies the correct status filter query parameter when clicked", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, limit: 50, offset: 0 }),
    } as any);

    render(<TraceList onSelectTrace={mockSelectTrace} onGoToOnboarding={mockGoToOnboarding} />);

    // Wait for initial fetch on mount
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("http://localhost:8000/v1/traces", expect.any(Object));
    });

    // Reset fetch mock to clear call history
    vi.mocked(global.fetch).mockClear();

    // Click "Errors" filter
    const errorBtn = screen.getByRole("button", { name: "Errors" });
    fireEvent.click(errorBtn);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("http://localhost:8000/v1/traces?status=error", expect.any(Object));
    });
  });

  it("triggers select trace navigation callback when a row is clicked", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: mockTraces, total: 2, limit: 50, offset: 0 }),
    } as any);

    render(<TraceList onSelectTrace={mockSelectTrace} onGoToOnboarding={mockGoToOnboarding} />);

    await waitFor(() => {
      expect(screen.getByText(/langchain/i)).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId("trace-row");
    fireEvent.click(rows[0]);
    expect(mockSelectTrace).toHaveBeenCalledWith("trace-1");
  });
});
