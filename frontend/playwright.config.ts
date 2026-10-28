import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 120000,
  workers: 1,
  retries: 0,
  outputDir: "test-results",
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: {
    baseURL: process.env.DOCUMIND_TEST_URL || "http://127.0.0.1:8765",
    channel: process.env.CI ? undefined : "chrome",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    video: "on",
    trace: "retain-on-failure",
  },
});
