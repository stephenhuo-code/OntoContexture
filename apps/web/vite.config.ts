import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

// 本地开发：/bff 代理到集群入口（make up 后的 http://localhost:8080），与生产同源
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    dedupe: ["react", "react-dom", "react-router", "react-router-dom"],
  },
  // 006：/assets 是数据资产页面的地址，构建产物改放 /static/，避免被静态目录规则截走
  build: { assetsDir: "static" },
  server: {
    port: 5173,
    proxy: { "/bff": "http://localhost:8080" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "json-summary", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/__tests__/**", "src/test-setup.ts"],
      thresholds: { lines: 80 },
    },
  },
});
