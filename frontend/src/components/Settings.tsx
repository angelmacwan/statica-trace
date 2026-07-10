import { useEffect, useState } from "react";
import { apiFetch, getApiKey, clearApiKey } from "../utils/api";

interface SettingsProps {
  onLogout: () => void;
}

export function Settings({ onLogout }: SettingsProps) {
  const [project, setProject] = useState<{ id: string; name: string; created_at: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const apiKey = getApiKey() || "";

  useEffect(() => {
    async function loadProject() {
      try {
        setLoading(true);
        const data = await apiFetch("/v1/projects/me");
        setProject(data);
        localStorage.setItem("statica_project_name", data.name);
      } catch (err: any) {
        setError(err.message || "Failed to load project details.");
      } finally {
        setLoading(false);
      }
    }
    loadProject();
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLogout = () => {
    clearApiKey();
    onLogout();
  };

  const formatKey = (key: string) => {
    if (!key) return "";
    if (key.length <= 8) return key;
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <span className="mt-4 text-sm text-secondary font-medium">Loading settings...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-error-container text-error rounded-xl p-4 font-medium max-w-2xl mx-auto border border-error/10">
        <h3 className="font-headline font-bold mb-2">Error Loading Settings</h3>
        <p className="text-sm">{error}</p>
        <button
          onClick={handleLogout}
          className="mt-4 inline-flex items-center justify-center rounded-lg px-4 py-2 bg-error text-on-error font-semibold text-xs transition hover:opacity-90"
        >
          Reset Session
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-headline font-extrabold text-primary tracking-tight">
          Project Settings
        </h1>
        <button
          onClick={handleLogout}
          className="inline-flex items-center justify-center rounded-lg px-4 py-2 bg-surface-container-high text-primary hover:bg-surface-container font-semibold text-xs transition"
        >
          Log Out
        </button>
      </div>

      <div className="bg-surface-container-lowest rounded-xl p-6 shadow-ambient-lg border border-surface-container-high/60 space-y-6">
        <div>
          <h2 className="text-lg font-headline font-bold text-primary mb-4 border-b border-surface-container-high/60 pb-2">
            Project Information
          </h2>
          <div className="grid grid-cols-3 gap-y-4 text-sm">
            <span className="text-secondary font-medium">Project Name:</span>
            <span className="col-span-2 text-primary font-bold">{project?.name}</span>

            <span className="text-secondary font-medium">Project ID:</span>
            <span className="col-span-2 font-mono text-xs text-primary bg-surface-container-low px-2 py-1 rounded w-fit select-all">
              {project?.id}
            </span>

            <span className="text-secondary font-medium">Created At:</span>
            <span className="col-span-2 text-on-surface-variant font-medium">
              {project?.created_at ? new Date(project.created_at).toLocaleString() : "N/A"}
            </span>
          </div>
        </div>

        <div>
          <h2 className="text-lg font-headline font-bold text-primary mb-4 border-b border-surface-container-high/60 pb-2">
            Security & Authentication
          </h2>
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wide text-secondary block">
              API Key
            </label>
            <div className="bg-surface-container-low rounded-xl p-4 flex items-center justify-between border border-surface-container">
              <code className="text-sm font-mono text-primary select-all">
                {showKey ? apiKey : formatKey(apiKey)}
              </code>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowKey(!showKey)}
                  className="px-3 py-1.5 text-xs text-secondary font-medium hover:text-primary transition"
                >
                  {showKey ? "Hide" : "Reveal"}
                </button>
                <button
                  onClick={handleCopy}
                  className="px-3 py-1.5 bg-surface-container-high text-primary hover:bg-surface-container text-xs font-semibold rounded-lg transition"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
            <p className="text-xs text-on-surface-variant">
              This API key grants write/ingestion permission to Statica Trace. Keep it confidential.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
