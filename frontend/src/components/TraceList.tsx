import { useEffect, useState } from "react";
import { apiFetch } from "../utils/api";

interface TraceListItem {
  trace_id: string;
  source: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
}

interface TraceListProps {
  onSelectTrace: (id: string) => void;
  onGoToOnboarding: () => void;
}

export function TraceList({ onSelectTrace, onGoToOnboarding }: TraceListProps) {
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">("all");

  useEffect(() => {
    async function fetchTraces() {
      try {
        setLoading(true);
        setError("");
        let path = "/v1/traces";
        if (statusFilter !== "all") {
          path += `?status=${statusFilter}`;
        }
        const data = await apiFetch(path);
        setTraces(data.items || []);
      } catch (err: any) {
        setError(err.message || "Failed to load traces.");
      } finally {
        setLoading(false);
      }
    }
    fetchTraces();
  }, [statusFilter]);

  const formatDuration = (ms: number | null) => {
    if (ms === null || ms === undefined) return "-";
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatTimestamp = (isoString: string | null) => {
    if (!isoString) return "-";
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-headline font-extrabold text-primary tracking-tight">
            Execution Traces
          </h1>
          <p className="text-sm text-on-surface-variant font-sans">
            Monitor and debug agent executions in real-time.
          </p>
        </div>

        {/* Filters */}
        <div className="flex bg-surface-container-low p-1 rounded-xl w-fit self-start sm:self-center border border-surface-container-high/40">
          {(["all", "success", "error"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition capitalize ${
                statusFilter === filter
                  ? "bg-surface-container-lowest text-primary shadow-ambient-sm font-bold"
                  : "text-secondary hover:text-primary"
              }`}
            >
              {filter === "all" ? "All Traces" : filter === "success" ? "Success" : "Errors"}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-error-container text-error rounded-xl p-4 font-medium border border-error/10 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="bg-surface-container-lowest rounded-xl border border-surface-container-high/60 overflow-hidden shadow-ambient-lg">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-gradient-to-b from-surface-container to-surface-container-low">
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Source
                </th>
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Status
                </th>
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-surface-container-high/60">
                  <td className="px-6 py-4.5">
                    <div className="h-4 bg-surface-container rounded w-36"></div>
                  </td>
                  <td className="px-6 py-4.5">
                    <div className="h-4 bg-surface-container rounded w-16"></div>
                  </td>
                  <td className="px-6 py-4.5">
                    <div className="h-6 bg-surface-container rounded-full w-20"></div>
                  </td>
                  <td className="px-6 py-4.5">
                    <div className="h-4 bg-surface-container rounded w-12"></div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : traces.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-xl p-12 text-center border border-surface-container-high/60 shadow-ambient-lg flex flex-col items-center max-w-xl mx-auto">
          <div className="w-12 h-12 rounded-xl bg-surface-container-low flex items-center justify-center text-secondary mb-4 border border-surface-container">
            📊
          </div>
          <h3 className="text-lg font-headline font-bold text-primary mb-2">
            No traces yet
          </h3>
          <p className="text-sm text-on-surface-variant mb-6 font-sans">
            We couldn't find any traces matching the selected filter. To start capturing agent traces, follow the integration instructions.
          </p>
          <button
            onClick={onGoToOnboarding}
            className="inline-flex items-center justify-center rounded-lg px-5 py-2.5 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold text-sm shadow-brand hover:opacity-90 transition active:scale-[0.98]"
          >
            View Setup Instructions
          </button>
        </div>
      ) : (
        <div className="bg-surface-container-lowest rounded-xl border border-surface-container-high/60 overflow-hidden shadow-ambient-lg">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-gradient-to-b from-surface-container to-surface-container-low">
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Source
                </th>
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Status
                </th>
                <th className="px-6 py-3 text-xs font-bold uppercase tracking-wide text-secondary text-left border-b border-surface-container-high">
                  Duration
                </th>
              </tr>
            </thead>
            <tbody>
              {traces.map((trace) => (
                <tr
                  key={trace.trace_id}
                  onClick={() => onSelectTrace(trace.trace_id)}
                  className="hover:bg-primary/[0.025] cursor-pointer transition border-b border-surface-container-high/60 active:bg-primary/[0.05]"
                  data-testid="trace-row"
                >
                  <td className="px-6 py-4 font-medium text-primary">
                    {formatTimestamp(trace.started_at)}
                  </td>
                  <td className="px-6 py-4 font-mono text-xs uppercase text-secondary">
                    {trace.source}
                  </td>
                  <td className="px-6 py-4">
                    {trace.status === "error" ? (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[0.65rem] font-bold uppercase tracking-wide bg-error-container text-error border border-error/10">
                        Error
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[0.65rem] font-bold uppercase tracking-wide bg-secondary-container text-on-secondary-container border border-secondary/10">
                        Success
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-on-surface-variant font-medium">
                    {formatDuration(trace.duration_ms)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
