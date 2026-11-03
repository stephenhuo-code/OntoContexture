import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    lib: { entry: "src/index.ts", formats: ["es"], fileName: "index" },
    rollupOptions: { external: [/^react($|\/)/, /^react-dom($|\/)/] },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx,js}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "json-summary", "lcov"],
      include: [
        "src/**/*.{ts,tsx}",
        "../../extensions/keycloak/themes/contexture/login/resources/js/contexture.js",
      ],
      allowExternal: true,
      exclude: ["src/**/__tests__/**", "src/test-setup.ts"],
      thresholds: { lines: 80 },
    },
  },
});
