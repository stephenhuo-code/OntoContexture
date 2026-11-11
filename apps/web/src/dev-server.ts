// Vite 开发服务器配置（030）：本地开发时 /bff 代理到 make up 的入口；云端开发模式（make cloud-dev）下页面经
// https://<域名> 访问，/bff 由集群入口直接转给 bff，Vite 只需放行织境域名并让 HMR 经 443 回连。
export interface DevServerOptions {
  port: number;
  proxy: Record<string, string>;
  allowedHosts?: string[];
  hmr?: { clientPort: number; protocol: "wss" };
}

export function devServer(env: Record<string, string | undefined>): DevServerOptions {
  const server: DevServerOptions = { port: 5173, proxy: { "/bff": "http://localhost:8080" } };
  const hosts = env.CTX_VITE_ALLOWED_HOSTS;
  if (hosts) {
    server.allowedHosts = hosts.split(",").map((h) => h.trim()).filter(Boolean);
    server.hmr = { clientPort: Number(env.CTX_VITE_HMR_CLIENT_PORT ?? 443), protocol: "wss" };
  }
  return server;
}
