import { describe, it, expect, vi, beforeEach } from "vitest";
import { getApiKey, setApiKey, clearApiKey, apiFetch } from "../utils/api";

describe("api utilities", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  describe("API key management", () => {
    it("manages api key in localStorage", () => {
      expect(getApiKey()).toBeNull();
      
      setApiKey("test-key");
      expect(getApiKey()).toBe("test-key");
      expect(localStorage.getItem("statica_api_key")).toBe("test-key");

      localStorage.setItem("statica_project_name", "test-project");
      clearApiKey();
      expect(getApiKey()).toBeNull();
      expect(localStorage.getItem("statica_project_name")).toBeNull();
    });
  });

  describe("apiFetch", () => {
    it("adds Bearer token and JSON headers when fetching", async () => {
      setApiKey("test-token");
      
      const mockResponse = { data: "success" };
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await apiFetch("/test-path", { method: "POST" });
      expect(result).toEqual(mockResponse);
      
      expect(fetchSpy).toHaveBeenCalledWith("http://localhost:8000/test-path", expect.objectContaining({
        method: "POST",
      }));
      
      const lastCallArgs = fetchSpy.mock.calls[0][1];
      const headers = lastCallArgs?.headers as Headers;
      expect(headers.get("Authorization")).toBe("Bearer test-token");
      expect(headers.get("Content-Type")).toBe("application/json");
    });

    it("does not override existing Content-Type or Authorization headers", async () => {
      setApiKey("test-token");
      
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as Response);

      const headers = new Headers();
      headers.set("Authorization", "custom-auth");
      headers.set("Content-Type", "custom-content");

      await apiFetch("/test-path", { headers });
      
      const lastCallArgs = fetchSpy.mock.calls[0][1];
      const sentHeaders = lastCallArgs?.headers as Headers;
      expect(sentHeaders.get("Authorization")).toBe("custom-auth");
      expect(sentHeaders.get("Content-Type")).toBe("custom-content");
    });

    it("throws error with detail message on failed request", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: "Bad Request Detail" }),
      } as Response);

      await expect(apiFetch("/error")).rejects.toThrow("Bad Request Detail");
    });

    it("throws error with statusText on failed request where json parsing fails", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => {
          throw new Error("Invalid JSON");
        },
      } as Response);

      await expect(apiFetch("/error-json")).rejects.toThrow("Internal Server Error");
    });

    it("throws error with stringified JSON if detail is missing in failed request", async () => {
      const responseObj = { foo: "bar" };
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => responseObj,
      } as Response);

      await expect(apiFetch("/error-no-detail")).rejects.toThrow(JSON.stringify(responseObj));
    });

    it("falls back to status code message if both json detail and statusText are empty", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "",
        json: async () => {
          throw new Error("Invalid JSON");
        },
      } as Response);

      await expect(apiFetch("/error-empty-all")).rejects.toThrow("Request failed with status 500");
    });
  });
});
