import { describe, expect, it } from "vitest";
import { devServer } from "./dev-server";

// 030：云端开发模式下 Vite 经 HTTPS 入口提供页面，HMR 走 443；未设置环境变量时与本地开发完全一致
describe("devServer", () => {
  it("本地默认：5173 端口，/bff 代理到 make up 的入口", () => {
    expect(devServer({})).toEqual({ port: 5173, proxy: { "/bff": "http://localhost:8080" } });
  });

  it("云端开发模式：允许织境域名，HMR 经 443 的 wss 回连", () => {
    const server = devServer({ CTX_VITE_ALLOWED_HOSTS: "ctx.example.com,www.ctx.example.com" });
    expect(server.allowedHosts).toEqual(["ctx.example.com", "www.ctx.example.com"]);
    expect(server.hmr).toEqual({ clientPort: 443, protocol: "wss" });
  });

  it("HMR 端口可配置", () => {
    const server = devServer({ CTX_VITE_ALLOWED_HOSTS: "ctx.example.com", CTX_VITE_HMR_CLIENT_PORT: "8443" });
    expect(server.hmr).toEqual({ clientPort: 8443, protocol: "wss" });
  });
});
