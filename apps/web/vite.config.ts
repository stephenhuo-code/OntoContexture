import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 本地开发：/bff 代理到集群入口（make up 后的 http://localhost:8080），与生产同源
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/bff": "http://localhost:8080" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
