const API_BASE = (import.meta.env.VITE_API_BASE as string) || 
  ((window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") 
    ? "http://localhost:8000" 
    : window.location.origin);

export function getApiKey(): string | null {
  return localStorage.getItem("statica_api_key");
}

export function setApiKey(key: string) {
  localStorage.setItem("statica_api_key", key);
}

export function clearApiKey() {
  localStorage.removeItem("statica_api_key");
  localStorage.removeItem("statica_project_name");
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  const apiKey = getApiKey();
  const headers = new Headers(options.headers || {});
  
  if (apiKey && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${apiKey}`);
  }
  
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearApiKey();
      window.dispatchEvent(new Event("auth_failure"));
    }
    let errorDetail = "";
    try {
      const data = await response.json();
      errorDetail = data.detail || JSON.stringify(data);
    } catch {
      errorDetail = response.statusText;
    }
    const message = errorDetail || `Request failed with status ${response.status}`;
    const error: any = new Error(message);
    error.status = response.status;
    throw error;
  }

  return response.json();
}
