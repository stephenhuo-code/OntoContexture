import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";
import { devServer } from "./src/dev-server";

// 配置文件在 Node 中执行；tsconfig 未引入 node 类型，按最小形状读取环境变量
const nodeEnv =
  (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};

// 本地开发：/bff 代理到集群入口（make up 后的 http://localhost:8080），与生产同源；云端开发模式见 src/dev-server.ts（030）
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    dedupe: ["react", "react-dom", "react-router", "react-router-dom"],
  },
  // 006：/assets 是数据资产页面的地址，构建产物改放 /static/，避免被静态目录规则截走
  build: { assetsDir: "static" },
  server: devServer(nodeEnv),
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
