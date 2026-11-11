import { defineConfig, devices } from "@playwright/test";

// 最终演示的浏览器端到端测试（T064）。需要 make up、make seed；入口 http://localhost:8080
export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  testIgnore: "ui-examples.spec.ts",
  outputDir: "../../test-results/production",
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    // 云端（030）：工具箱中由 CTX_E2E_BASE_URL 指向 https://<域名>
    baseURL: process.env.CTX_E2E_BASE_URL ?? "http://localhost:8080",
    // 本机 Keycloak 经 Paperclip 的 Caddy，证书由其本地 CA 签发
    ignoreHTTPSErrors: true,
    locale: "zh-CN",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
