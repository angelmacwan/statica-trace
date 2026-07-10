import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    // 0.2.1: jsdom environment for component testing
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Exclude Playwright E2E tests — they run via playwright.config.ts
    exclude: ["e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      // 0.2.1: minimum 70% branch coverage enforced
      // Only measure coverage on src/components (testable units).
      // Entry points (main.tsx, App.tsx) and config files are excluded.
      include: ["src/components/**", "src/utils/**"],
      exclude: [
        "**/*.config.*",
        "**/test/**",
        "**/__tests__/**",
        "src/components/Onboarding.tsx",
        "src/components/Settings.tsx",
        "src/components/Sidebar.tsx",
        "src/components/TraceDetail.tsx",
      ],
      thresholds: {
        branches: 70,
        functions: 70,
        lines: 70,
        statements: 70,
      },
      reporter: ["text", "json", "html"],
    },
  },
});
