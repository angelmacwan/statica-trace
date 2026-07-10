import { useState } from "react";
import { apiFetch, setApiKey } from "../utils/api";

interface OnboardingProps {
  onSuccess: (key: string) => void;
}

export function Onboarding({ onSuccess }: OnboardingProps) {
  const [mode, setMode] = useState<"create" | "existing">("create");
  const [projectName, setProjectName] = useState("");
  const [pastedKey, setPastedKey] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const [createdProjectName, setCreatedProjectName] = useState("");
  const [activeTab, setActiveTab] = useState<"langchain" | "openai" | "otel">("langchain");
  const [showKey, setShowKey] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) return;

    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: projectName }),
      });
      setCreatedKey(data.api_key);
      setCreatedProjectName(data.name);
      setApiKey(data.api_key);
    } catch (err: any) {
      setError(err.message || "Failed to create project.");
    } finally {
      setLoading(false);
    }
  };

  const handleExistingKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pastedKey.trim()) return;

    setLoading(true);
    setError("");
    try {
      // Temporarily store to perform authentication verification
      localStorage.setItem("statica_api_key", pastedKey);
      const data = await apiFetch("/v1/projects/me");
      // Key verified successfully
      setApiKey(pastedKey);
      onSuccess(pastedKey);
    } catch (err: any) {
      localStorage.removeItem("statica_api_key");
      setError("Invalid API key. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(id);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const formatKey = (key: string) => {
    if (!key) return "";
    if (key.length <= 8) return key;
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  };

  const getSnippets = (key: string) => {
    const displayKey = key || "YOUR_STATICA_API_KEY";
    return {
      langchain: `from agentreplay.langchain import AgentReplayCallbackHandler
from langchain_openai import ChatOpenAI

# 1. Initialize callback handler
handler = AgentReplayCallbackHandler(api_key="${displayKey}")

# 2. Attach handler to run configs
llm = ChatOpenAI(model="gpt-4o")
chain = prompt | llm

chain.invoke(
    {"input": "Hello!"},
    config={"callbacks": [handler]}
)`,
      openai: `import openai
from agentreplay.openai_wrapper import wrap

# Wrap the client transparently
client = wrap(openai.OpenAI(api_key="your_openai_key"))

# Calls are intercepted and recorded, returning normal API response types
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)`,
      otel: `from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from agentreplay.otel_exporter import AgentReplayOTelExporter

# 1. Configure the exporter pointing to Statica Trace
exporter = AgentReplayOTelExporter(
    api_key="${displayKey}",
    endpoint="http://localhost:8000/v1/ingest"
)

# 2. Add processor to TracerProvider
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)`
    };
  };

  const snippets = getSnippets(createdKey);

  if (createdKey) {
    return (
      <div className="min-h-screen bg-surface flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="bg-surface-container-lowest max-w-3xl w-full rounded-[2rem] p-8 shadow-ambient-lg border border-surface-container-high/60">
          <div className="text-center mb-8">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide bg-secondary-container text-primary mb-3">
              Project Created
            </span>
            <h2 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
              Welcome to {createdProjectName}
            </h2>
            <p className="mt-2 text-sm text-on-surface-variant font-sans">
              Here is your project API key and setup instructions. Store it securely.
            </p>
          </div>

          <div className="bg-surface-container-low rounded-xl p-4 flex items-center justify-between border border-surface-container mb-8">
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-widest text-secondary mb-1">
                API Key
              </span>
              <code className="text-sm font-mono text-primary select-all" data-testid="api-key-display">
                {showKey ? createdKey : formatKey(createdKey)}
              </code>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowKey(!showKey)}
                className="px-3 py-1.5 text-xs text-secondary font-medium hover:text-primary transition"
              >
                {showKey ? "Hide" : "Reveal"}
              </button>
              <button
                onClick={() => handleCopy(createdKey, "apikey")}
                className="px-3 py-1.5 bg-surface-container-high text-primary hover:bg-surface-container text-xs font-semibold rounded-lg transition"
              >
                {copiedIndex === "apikey" ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-headline font-bold text-primary mb-4">
              Integrate with Your Agent Framework
            </h3>

            {/* Tab navigation */}
            <div className="flex border-b border-surface-container-high/60 mb-4">
              {(["langchain", "openai", "otel"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-sm font-semibold border-b-2 transition capitalize ${
                    activeTab === tab
                      ? "border-primary text-primary"
                      : "border-transparent text-secondary hover:text-primary"
                  }`}
                >
                  {tab === "otel" ? "OpenTelemetry" : tab}
                </button>
              ))}
            </div>

            {/* Code block */}
            <div className="relative">
              <pre className="bg-primary text-on-primary font-mono text-xs p-5 rounded-xl overflow-x-auto leading-relaxed shadow-hero">
                <code>{snippets[activeTab]}</code>
              </pre>
              <button
                onClick={() => handleCopy(snippets[activeTab], activeTab)}
                className="absolute top-3 right-3 px-3 py-1.5 bg-primary-container text-on-primary hover:opacity-90 text-xs font-semibold rounded-lg shadow-ambient-sm transition"
              >
                {copiedIndex === activeTab ? "Copied!" : "Copy Snippet"}
              </button>
            </div>
          </div>

          <div className="mt-8 flex justify-end">
            <button
              onClick={() => onSuccess(createdKey)}
              className="inline-flex items-center justify-center rounded-lg px-6 py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold text-sm shadow-brand hover:opacity-90 transition active:scale-[0.98]"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="bg-surface-container-lowest max-w-md w-full rounded-[2rem] p-8 shadow-ambient-lg border border-surface-container-high/60">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-headline font-bold text-xl mb-4 shadow-brand">
            S
          </div>
          <h1 className="text-3xl font-headline font-extrabold text-primary tracking-tight">
            Statica Trace
          </h1>
          <p className="mt-2 text-sm text-on-surface-variant font-sans">
            AI Agent trace capture and replay debugger
          </p>
        </div>

        {/* Tab switch */}
        <div className="grid grid-cols-2 bg-surface-container-low p-1 rounded-xl mb-6">
          <button
            onClick={() => {
              setMode("create");
              setError("");
            }}
            className={`py-2 text-xs font-semibold rounded-lg transition ${
              mode === "create"
                ? "bg-surface-container-lowest text-primary shadow-ambient-sm font-bold"
                : "text-secondary hover:text-primary"
            }`}
          >
            Create Project
          </button>
          <button
            onClick={() => {
              setMode("existing");
              setError("");
            }}
            className={`py-2 text-xs font-semibold rounded-lg transition ${
              mode === "existing"
                ? "bg-surface-container-lowest text-primary shadow-ambient-sm font-bold"
                : "text-secondary hover:text-primary"
            }`}
          >
            I have an API Key
          </button>
        </div>

        {error && (
          <div className="bg-error-container text-error rounded-xl p-3 text-xs mb-6 font-medium border border-error/10">
            {error}
          </div>
        )}

        {mode === "create" ? (
          <form onSubmit={handleCreateProject} className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-secondary mb-2 block">
                Project Name
              </label>
              <input
                type="text"
                required
                disabled={loading}
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. customer-service-agent"
                className="w-full rounded-lg px-4 py-3 bg-surface-container-low text-on-surface placeholder:text-outline text-[0.9375rem] outline-none focus:ring-2 focus:ring-primary/30 border border-transparent transition"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !projectName.trim()}
              className="w-full inline-flex items-center justify-center rounded-lg px-6 py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold text-sm shadow-brand hover:opacity-90 transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Creating..." : "Create Project"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleExistingKey} className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-secondary mb-2 block">
                Statica API Key
              </label>
              <input
                type="text"
                required
                disabled={loading}
                value={pastedKey}
                onChange={(e) => setPastedKey(e.target.value)}
                placeholder="statica_..."
                className="w-full rounded-lg px-4 py-3 bg-surface-container-low text-on-surface placeholder:text-outline text-[0.9375rem] outline-none focus:ring-2 focus:ring-primary/30 border border-transparent transition"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !pastedKey.trim()}
              className="w-full inline-flex items-center justify-center rounded-lg px-6 py-3 bg-gradient-to-br from-primary to-primary-container text-on-primary font-semibold text-sm shadow-brand hover:opacity-90 transition active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Verifying..." : "Access Dashboard"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
