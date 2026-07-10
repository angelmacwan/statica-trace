import { useEffect, useState } from "react";
import { apiFetch } from "../utils/api";
import { buildSpanTree, flattenSpanTree, SpanTreeNode } from "../utils/spanTree";

interface TraceDetailProps {
  traceId: string;
  onBack: () => void;
  onReplayClick: (span: SpanTreeNode) => void;
}

export function TraceDetail({ traceId, onBack, onReplayClick }: TraceDetailProps) {
  const [trace, setTrace] = useState<any>(null);
  const [spans, setSpans] = useState<SpanTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedSpanId, setExpandedSpanId] = useState<string | null>(null);

  useEffect(() => {
    async function fetchTraceDetail() {
      try {
        setLoading(true);
        setError("");
        const data = await apiFetch(`/v1/traces/${traceId}`);
        setTrace(data);
        const tree = buildSpanTree(data.spans || []);
        const flatTree = flattenSpanTree(tree);
        setSpans(flatTree);
      } catch (err: any) {
        setError(err.message || "Failed to load trace detail.");
      } finally {
        setLoading(false);
      }
    }
    fetchTraceDetail();
  }, [traceId]);

  const toggleExpand = (spanId: string) => {
    setExpandedSpanId(expandedSpanId === spanId ? null : spanId);
  };

  const getSpanIcon = (type: string) => {
    switch (type) {
      case "llm_call":
        return "🧠";
      case "tool_call":
        return "🛠️";
      case "retrieval":
        return "🔍";
      case "agent_step":
        return "🔄";
      default:
        return "📄";
    }
  };

  const formatDuration = (start: string, end: string) => {
    const s = new Date(start).getTime();
    const e = new Date(end).getTime();
    const ms = e - s;
    if (isNaN(ms) || ms < 0) return "-";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <span className="mt-4 text-sm text-secondary font-medium">Loading trace details...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-error-container text-error rounded-xl p-4 font-medium border border-error/10 text-sm max-w-2xl mx-auto space-y-4">
        <h3 className="font-headline font-bold">Error Loading Trace</h3>
        <p>{error}</p>
        <button
          onClick={onBack}
          className="inline-flex items-center justify-center rounded-lg px-4 py-2 bg-error text-on-error font-semibold text-xs transition hover:opacity-90"
        >
          Back to List
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Navigation & Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-surface-container-low text-primary hover:bg-surface-container transition"
          aria-label="Back to Traces"
        >
          ←
        </button>
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-secondary font-mono">
            <span>Traces</span>
            <span>/</span>
            <span className="text-primary truncate max-w-[200px]">{traceId}</span>
          </div>
          <h1 className="text-xl font-headline font-bold text-primary tracking-tight">
            Trace Timeline
          </h1>
        </div>
      </div>

      {/* Trace Metadata Card */}
      <div className="bg-surface-container-lowest rounded-xl p-4 shadow-ambient-lg border border-surface-container-high/60 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-secondary block font-medium mb-0.5">Source</span>
          <span className="font-bold font-mono text-primary uppercase">{trace?.source}</span>
        </div>
        <div>
          <span className="text-secondary block font-medium mb-0.5">Status</span>
          {trace?.status === "error" ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-error-container text-error">
              Error
            </span>
          ) : (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-secondary-container text-on-secondary-container">
              Success
            </span>
          )}
        </div>
        <div>
          <span className="text-secondary block font-medium mb-0.5">Started At</span>
          <span className="text-primary font-medium">
            {trace?.started_at ? new Date(trace.started_at).toLocaleString() : "-"}
          </span>
        </div>
        <div>
          <span className="text-secondary block font-medium mb-0.5">Total Spans</span>
          <span className="text-primary font-bold">{trace?.spans?.length || 0}</span>
        </div>
      </div>

      {/* Timeline View */}
      {spans.length === 0 ? (
        <div className="bg-surface-container-lowest rounded-xl p-12 text-center border border-surface-container-high/60 shadow-ambient-lg">
          <p className="text-sm text-secondary font-medium font-sans">
            No spans found for this trace.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {spans.map((node) => {
            const isExpanded = expandedSpanId === node.span_id;
            const isError = !!node.error;
            const paddingLeft = `${node.depth * 24}px`;

            return (
              <div
                key={node.span_id}
                className="bg-surface-container-lowest rounded-xl border border-surface-container-high/60 overflow-hidden shadow-ambient-sm transition hover:shadow-ambient-lg"
              >
                {/* Row Header */}
                <div
                  onClick={() => toggleExpand(node.span_id)}
                  className={`flex items-center justify-between p-4 cursor-pointer select-none transition ${
                    isExpanded ? "bg-surface-container-low" : "hover:bg-primary/[0.015]"
                  } ${isError ? "border-l-4 border-error" : ""}`}
                  style={{ paddingLeft: `calc(1rem + ${paddingLeft})` }}
                  data-testid="span-row"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{getSpanIcon(node.type)}</span>
                    <div>
                      <h4 className="font-semibold text-sm text-primary flex items-center gap-2">
                        {node.name}
                        {isError && (
                          <span className="inline-flex px-1.5 py-0.5 bg-error-container text-error text-[9px] font-bold rounded uppercase">
                            Error
                          </span>
                        )}
                      </h4>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                        {node.type.replace("_", " ")}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <span className="text-xs text-secondary font-semibold font-mono">
                      {formatDuration(node.started_at, node.ended_at)}
                    </span>
                    <span className="text-secondary text-xs transition">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  </div>
                </div>

                {/* Expanded Details Section */}
                {isExpanded && (
                  <div className="border-t border-surface-container-high/60 bg-surface-bright/40 p-4 space-y-4 text-xs font-sans">
                    {isError && (
                      <div className="bg-error-container/40 border border-error/20 text-error rounded-lg p-3">
                        <span className="font-bold block mb-1">Execution Failure:</span>
                        <pre className="font-mono text-xs whitespace-pre-wrap">{node.error}</pre>
                      </div>
                    )}

                    {/* Inputs and Outputs split grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Left: Input parameters / context */}
                      <div className="space-y-3">
                        <h5 className="font-bold text-primary uppercase tracking-wide text-[10px]">
                          Input Payload
                        </h5>

                        {node.type === "llm_call" && node.input ? (
                          <div className="space-y-3">
                            {node.input.model && (
                              <div>
                                <span className="text-secondary block font-medium mb-1">Model</span>
                                <code className="bg-surface-container px-2 py-0.5 rounded text-primary font-mono font-bold">
                                  {node.input.model}
                                </code>
                              </div>
                            )}

                            {node.input.params && (
                              <div>
                                <span className="text-secondary block font-medium mb-1">Parameters</span>
                                <div className="flex flex-wrap gap-2">
                                  {Object.entries(node.input.params).map(([k, v]: any) => (
                                    <span key={k} className="bg-surface-container px-2 py-0.5 rounded text-secondary font-semibold">
                                      {k}: {v}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {node.input.messages && (
                              <div className="space-y-2">
                                <span className="text-secondary block font-medium">Prompt Messages</span>
                                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                                  {node.input.messages.map((m: any, idx: number) => {
                                    const isSystem = m.role === "system";
                                    const isUser = m.role === "user";
                                    return (
                                      <div
                                        key={idx}
                                        className={`p-2.5 rounded-xl border ${
                                          isSystem
                                            ? "bg-surface-container border-surface-container-high/60 text-secondary"
                                            : isUser
                                            ? "bg-primary/[0.03] border-primary/10 text-primary"
                                            : "bg-secondary-container/20 border-secondary/10 text-secondary"
                                        }`}
                                      >
                                        <div className="font-bold text-[9px] uppercase tracking-wider mb-1">
                                          {m.role}
                                        </div>
                                        <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            {node.input.tools && (
                              <div>
                                <span className="text-secondary block font-medium mb-1">Tool Schemas</span>
                                <pre className="bg-surface-container p-2.5 rounded-lg overflow-x-auto text-[10px] font-mono text-secondary">
                                  {JSON.stringify(node.input.tools, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        ) : (
                          // For other types, dump the raw input nicely
                          <pre className="bg-surface-container p-3 rounded-lg overflow-x-auto font-mono text-secondary max-h-[300px]">
                            {JSON.stringify(node.input || {}, null, 2)}
                          </pre>
                        )}
                      </div>

                      {/* Right: Outputs */}
                      <div className="space-y-3">
                        <div className="flex justify-between items-center">
                          <h5 className="font-bold text-primary uppercase tracking-wide text-[10px]">
                            Output Payload
                          </h5>
                          {node.type === "llm_call" && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onReplayClick(node);
                              }}
                              className="px-3 py-1 bg-gradient-to-br from-primary to-primary-container text-on-primary text-xs font-bold rounded-lg shadow-brand hover:opacity-90 transition active:scale-[0.98]"
                            >
                              Replay Debugger
                            </button>
                          )}
                        </div>

                        {node.type === "llm_call" && node.output ? (
                          <div className="space-y-3">
                            {node.output.content && (
                              <div>
                                <span className="text-secondary block font-medium mb-1">Completion Text</span>
                                <div className="bg-surface-container p-3 rounded-xl whitespace-pre-wrap leading-relaxed text-primary">
                                  {node.output.content}
                                </div>
                              </div>
                            )}

                            {node.output.tool_calls && node.output.tool_calls.length > 0 && (
                              <div>
                                <span className="text-secondary block font-medium mb-1">Outbound Tool Calls</span>
                                <div className="space-y-2">
                                  {node.output.tool_calls.map((tc: any, tcIdx: number) => (
                                    <div key={tcIdx} className="bg-surface-container p-2.5 rounded-lg border border-surface-container-high/60">
                                      <div className="font-bold text-primary text-[10px] uppercase font-mono mb-1">
                                        call: {tc.name}
                                      </div>
                                      <pre className="font-mono text-[10px] text-secondary overflow-x-auto">
                                        {JSON.stringify(tc.arguments, null, 2)}
                                      </pre>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          // For other types, dump the raw output nicely
                          <pre className="bg-surface-container p-3 rounded-lg overflow-x-auto font-mono text-secondary max-h-[300px]">
                            {JSON.stringify(node.output || {}, null, 2)}
                          </pre>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
