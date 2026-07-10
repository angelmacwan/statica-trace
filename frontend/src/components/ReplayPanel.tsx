import { useState } from "react";
import { apiFetch } from "../utils/api";
import { diffWords } from "../utils/diff";

interface Message {
  role: string;
  content: string;
}

interface ReplayPanelProps {
  traceId: string;
  span: {
    span_id: string;
    input?: {
      model?: string;
      messages?: Message[];
      params?: {
        temperature?: number;
        max_tokens?: number;
        [key: string]: any;
      };
      context?: string[] | any;
      documents?: string[] | any;
      [key: string]: any;
    };
    output?: {
      content?: string | null;
      tool_calls?: any[];
      [key: string]: any;
    };
    [key: string]: any;
  };
  onClose: () => void;
}

export function ReplayPanel({ traceId, span, onClose }: ReplayPanelProps) {
  const [model, setModel] = useState(span.input?.model || "gpt-4o-mini");
  const [messages, setMessages] = useState<Message[]>(() => {
    return span.input?.messages ? JSON.parse(JSON.stringify(span.input.messages)) : [];
  });
  const [temperature, setTemperature] = useState(span.input?.params?.temperature ?? 0.7);
  const [maxTokens, setMaxTokens] = useState(span.input?.params?.max_tokens ?? 1024);
  const [providerKey, setProviderKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [replayResult, setReplayResult] = useState<any>(null);

  // Initialize context blocks from input
  const [contextBlocks, setContextBlocks] = useState<string[]>(() => {
    const rawContext = span.input?.context || span.input?.documents;
    if (Array.isArray(rawContext)) {
      return rawContext.map(b => (typeof b === "string" ? b : JSON.stringify(b)));
    }
    if (typeof rawContext === "string") return [rawContext];
    return [];
  });

  const handleMessageChange = (index: number, content: string) => {
    const next = [...messages];
    next[index] = { ...next[index], content };
    setMessages(next);
  };

  const handleContextBlockChange = (index: number, content: string) => {
    const next = [...contextBlocks];
    next[index] = content;
    setContextBlocks(next);
  };

  const handleReplay = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!providerKey.trim()) {
      setError("Provider API key is required to execute a replay.");
      return;
    }

    setLoading(true);
    setError("");
    setReplayResult(null);

    // Reconstruct the edited input payload
    const editedInput: any = {
      model,
      messages,
      params: {
        temperature: Number(temperature),
        max_tokens: Number(maxTokens),
      },
    };

    if (contextBlocks.length > 0) {
      if (span.input?.context) {
        editedInput.context = contextBlocks;
      } else {
        editedInput.documents = contextBlocks;
      }
    }

    try {
      const response = await apiFetch("/v1/replay", {
        method: "POST",
        body: JSON.stringify({
          trace_id: traceId,
          span_id: span.span_id,
          edited_input: editedInput,
        }),
        headers: {
          "X-Provider-Api-Key": providerKey.trim(),
        },
      });
      setReplayResult(response);
    } catch (err: any) {
      setError(err.message || "An error occurred during replay execution.");
    } finally {
      setLoading(false);
    }
  };

  // Get original completion text
  const originalText = span.output?.content || "";
  // Get replayed completion text
  const replayedText = replayResult?.replayed_output?.content || "";

  const diffResult = diffWords(originalText, replayedText);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45 backdrop-blur-sm" data-testid="replay-panel">
      {/* Backdrop click closer */}
      <div className="flex-1" onClick={onClose}></div>

      {/* Slide-over panel */}
      <div className="w-full max-w-4xl bg-surface-container-lowest h-full shadow-hero flex flex-col border-l border-surface-container-high">
        {/* Header */}
        <div className="p-6 border-b border-surface-container-high/60 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-headline font-bold text-primary tracking-tight">
              Replay Debugger
            </h2>
            <span className="text-xs text-secondary font-semibold font-mono">
              Span: {span.name} ({span.span_id})
            </span>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-surface-container hover:bg-surface-container-high transition flex items-center justify-center text-primary text-sm font-bold"
            aria-label="Close panel"
          >
            ✕
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="bg-error-container text-error rounded-xl p-4 font-medium border border-error/10 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleReplay} className="space-y-6">
            {/* API Key */}
            <div className="bg-primary/[0.03] border border-primary/10 rounded-xl p-4 space-y-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-secondary block mb-1.5">
                  LLM Provider API Key (Required, Temporary)
                </label>
                <input
                  type="password"
                  required
                  disabled={loading}
                  value={providerKey}
                  onChange={(e) => setProviderKey(e.target.value)}
                  placeholder="sk-... or similar"
                  className="w-full rounded-lg px-4 py-2.5 bg-surface-container-lowest text-on-surface placeholder:text-outline text-sm outline-none focus:ring-2 focus:ring-primary/30 border border-surface-container-high transition"
                  data-testid="provider-key-input"
                />
              </div>
              <p className="text-[10px] text-on-surface-variant font-medium">
                🔑 Note: This key is used strictly for this direct API invocation to routing provider and is never stored on disk or database.
              </p>
            </div>

            {/* Model & Parameters */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-secondary mb-2 block">
                  Model
                </label>
                <input
                  type="text"
                  disabled={loading}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full rounded-lg px-4 py-2.5 bg-surface-container-low text-on-surface text-sm outline-none focus:ring-2 focus:ring-primary/30 border border-surface-container transition"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-secondary mb-2 block">
                  Temperature
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  disabled={loading}
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value) || 0)}
                  className="w-full rounded-lg px-4 py-2.5 bg-surface-container-low text-on-surface text-sm outline-none focus:ring-2 focus:ring-primary/30 border border-surface-container transition"
                />
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-secondary mb-2 block">
                  Max Tokens
                </label>
                <input
                  type="number"
                  min="1"
                  disabled={loading}
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value) || 0)}
                  className="w-full rounded-lg px-4 py-2.5 bg-surface-container-low text-on-surface text-sm outline-none focus:ring-2 focus:ring-primary/30 border border-surface-container transition"
                />
              </div>
            </div>

            {/* Messages */}
            {messages.length > 0 && (
              <div className="space-y-4">
                <h3 className="font-headline font-bold text-sm text-primary border-b border-surface-container-high pb-2">
                  System & Prompt Messages
                </h3>
                <div className="space-y-4">
                  {messages.map((msg, index) => (
                    <div key={index} className="space-y-1.5">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-secondary capitalize">
                        {msg.role} Message
                      </label>
                      <textarea
                        disabled={loading}
                        rows={3}
                        value={msg.content}
                        onChange={(e) => handleMessageChange(index, e.target.value)}
                        className="w-full rounded-lg p-3 bg-surface-container-low text-on-surface text-sm outline-none focus:ring-2 focus:ring-primary/30 border border-surface-container transition font-mono leading-relaxed"
                        data-testid={`message-input-${index}`}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Context Blocks */}
            {contextBlocks.length > 0 && (
              <div className="space-y-4">
                <h3 className="font-headline font-bold text-sm text-primary border-b border-surface-container-high pb-2">
                  Retrieved Context Blocks
                </h3>
                <div className="space-y-4">
                  {contextBlocks.map((block, index) => (
                    <div key={index} className="space-y-1.5">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-secondary">
                        Block #{index + 1}
                      </label>
                      <textarea
                        disabled={loading}
                        rows={3}
                        value={block}
                        onChange={(e) => handleContextBlockChange(index, e.target.value)}
                        className="w-full rounded-lg p-3 bg-surface-container-low text-on-surface text-sm outline-none focus:ring-2 focus:ring-primary/30 border border-surface-container transition font-mono text-xs leading-relaxed"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Trigger Button */}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={loading || !providerKey.trim()}
                className="inline-flex items-center justify-center rounded-lg px-6 py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold text-sm shadow-brand hover:opacity-90 transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="replay-submit-btn"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-on-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Executing Replay...
                  </>
                ) : (
                  "Run Replay"
                )}
              </button>
            </div>
          </form>

          {/* Replay Results / Visual Diff */}
          {replayResult && (
            <div className="space-y-4 border-t border-surface-container-high/60 pt-6" data-testid="diff-view">
              <h3 className="font-headline font-extrabold text-lg text-primary">
                Output Comparison
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Original completion */}
                <div className="bg-surface-container-low rounded-xl p-4 border border-surface-container-high/60">
                  <h4 className="font-bold text-xs text-secondary uppercase tracking-wide mb-2">
                    Original Output
                  </h4>
                  <div className="bg-surface-container-lowest p-3 rounded-lg font-mono text-xs text-primary min-h-[120px] whitespace-pre-wrap leading-relaxed">
                    {originalText || <span className="text-outline italic">No text content</span>}
                  </div>
                </div>

                {/* Replayed completion with highlighting */}
                <div className="bg-surface-container-low rounded-xl p-4 border border-surface-container-high/60">
                  <h4 className="font-bold text-xs text-secondary uppercase tracking-wide mb-2">
                    Replayed Output (Diffed)
                  </h4>
                  <div className="bg-surface-container-lowest p-3 rounded-lg font-mono text-xs text-primary min-h-[120px] whitespace-pre-wrap leading-relaxed">
                    {diffResult.length === 0 ? (
                      <span className="text-outline italic">No text content</span>
                    ) : (
                      diffResult.map((part, idx) => {
                        if (part.added) {
                          return (
                            <span key={idx} className="bg-emerald-100 text-emerald-800 font-bold px-0.5 rounded">
                              {part.value}
                            </span>
                          );
                        }
                        if (part.removed) {
                          return (
                            <span key={idx} className="bg-red-100 text-red-800 line-through px-0.5 rounded opacity-60">
                              {part.value}
                            </span>
                          );
                        }
                        return <span key={idx}>{part.value}</span>;
                      })
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
