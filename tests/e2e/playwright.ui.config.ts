import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: ".",
  testMatch: "ui-examples.spec.ts",
  timeout: 60_000,
  outputDir: "../../test-results/ui",
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    ignoreHTTPSErrors: true,
    locale: "zh-CN",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium-ui", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command:
      "pnpm --filter @contexture/web dev --host localhost --port 5173 --strictPort",
    url: "http://localhost:5173",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
