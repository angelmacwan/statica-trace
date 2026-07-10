const API_BASE = "http://localhost:8000";

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
    let errorDetail = "";
    try {
      const data = await response.json();
      errorDetail = data.detail || JSON.stringify(data);
    } catch {
      errorDetail = response.statusText;
    }
    throw new Error(errorDetail || `Request failed with status ${response.status}`);
  }

  return response.json();
}
