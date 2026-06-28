import { defineConfig } from "vitest/config";

// Dedicated Vitest config (kept separate from vite.config.ts so the PWA plugin doesn't run during
// tests). The runner logic is pure + Node-only (it validates the Answer Log against the contract
// via node:fs), so the test environment is Node, not jsdom.
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/runner/**/*.test.ts", "src/voice/**/*.test.ts", "src/sync/**/*.test.ts"],
  },
});
