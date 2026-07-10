import { useState, useEffect } from "react";
import { getApiKey } from "./utils/api";
import { Sidebar } from "./components/Sidebar";
import { Onboarding } from "./components/Onboarding";
import { TraceList } from "./components/TraceList";
import { TraceDetail } from "./components/TraceDetail";
import { Settings } from "./components/Settings";
import { ReplayPanel } from "./components/ReplayPanel";

export default function App() {
  const [apiKey, setApiKeyVal] = useState<string | null>(() => getApiKey());
  const [currentPath, setCurrentPath] = useState(window.location.pathname);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [replaySpan, setReplaySpan] = useState<any>(null);

  const navigate = (path: string) => {
    window.history.pushState(null, "", path);
    setCurrentPath(path);
  };

  // Watch for history state path shifts
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Listen for global auth failure events (401)
  useEffect(() => {
    const handleAuthFailure = () => {
      setApiKeyVal(null);
      navigate("/");
    };
    window.addEventListener("auth_failure", handleAuthFailure);
    return () => window.removeEventListener("auth_failure", handleAuthFailure);
  }, []);

  const handleAuthSuccess = (key: string) => {
    setApiKeyVal(key);
    navigate("/traces");
  };

  const handleLogout = () => {
    setApiKeyVal(null);
    navigate("/");
  };

  // If path is root and we have an API key, auto-redirect to traces
  useEffect(() => {
    if (apiKey && currentPath === "/") {
      navigate("/traces");
    } else if (!apiKey && currentPath !== "/") {
      navigate("/");
    }
  }, [apiKey, currentPath]);

  // Determine active route rendering
  const renderContent = () => {
    if (!apiKey) {
      return <Onboarding onSuccess={handleAuthSuccess} />;
    }

    if (currentPath === "/settings") {
      return <Settings onLogout={handleLogout} />;
    }

    if (currentPath === "/onboarding") {
      return <Onboarding onSuccess={() => navigate("/traces")} />;
    }

    if (currentPath.startsWith("/traces/")) {
      const traceId = currentPath.substring("/traces/".length);
      return (
        <TraceDetail
          traceId={traceId}
          onBack={() => navigate("/traces")}
          onReplayClick={(span) => setReplaySpan(span)}
        />
      );
    }

    // Default to TraceList for any other path (like /traces or /)
    return (
      <TraceList
        onSelectTrace={(id) => navigate(`/traces/${id}`)}
        onGoToOnboarding={() => navigate("/onboarding")}
      />
    );
  };

  if (!apiKey) {
    return <main className="min-h-screen bg-surface">{renderContent()}</main>;
  }

  // Active trace ID extracted from current path for Replay Panel
  const activeTraceId = currentPath.startsWith("/traces/")
    ? currentPath.substring("/traces/".length)
    : "";

  return (
    <div className="flex h-screen bg-surface text-on-surface overflow-hidden font-sans">
      {/* Sidebar navigation */}
      <Sidebar
        currentPath={currentPath}
        onNavigate={navigate}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main app block */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile Header */}
        <header className="h-16 shrink-0 border-b border-surface-container-high/60 bg-surface-container-lowest px-4 flex items-center justify-between tablet:hidden">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-surface-container text-primary font-bold text-xl"
              aria-label="Open Sidebar"
            >
              ☰
            </button>
            <span className="font-headline font-extrabold text-sm text-primary tracking-tight">
              Statica Trace
            </span>
          </div>
        </header>

        {/* Scrollable page body */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-8">
          {renderContent()}
        </main>
      </div>

      {/* Replay Panel Drawer */}
      {replaySpan && (
        <ReplayPanel
          traceId={activeTraceId}
          span={replaySpan}
          onClose={() => setReplaySpan(null)}
        />
      )}
    </div>
  );
}
