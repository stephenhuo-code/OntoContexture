import { afterEach, expect, it, vi } from "vitest";
import { loadMe, logout, loginUrl } from "../api";

afterEach(() => vi.unstubAllGlobals());
it("通过生成客户端同源读取身份并传递取消信号", async () => {
  const request = vi.fn(
    async (_request: Request) =>
      new Response(JSON.stringify({ tenant_id: "local", user_id: "u" }), {
        status: 200,
      }),
  );
  vi.stubGlobal("fetch", request);
  const abort = new AbortController();
  expect((await loadMe(abort.signal)).user_id).toBe("u");
  const sent = request.mock.calls[0]?.[0] as unknown as Request;
  expect(new URL(sent.url).pathname).toBe("/bff/v1/me");
  expect(sent.credentials).toBe("same-origin");
  abort.abort();
  expect(sent.signal.aborted).toBe(true);
});
it.each([401, 403, 500, 502])("保留 HTTP %s 状态", async (status) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("<html>gateway</html>", { status })),
  );
  await expect(loadMe()).rejects.toMatchObject({ status });
});
it("网络失败可区分于身份失效", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw Error("offline");
    }),
  );
  await expect(loadMe()).rejects.toMatchObject({ status: 0 });
});
it("退出只有 204 才算完成", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("private failure", { status: 500 })),
  );
  await expect(logout()).rejects.toMatchObject({ status: 500 });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(null, { status: 204 })),
  );
  await expect(logout()).resolves.toBeUndefined();
});
it.each([
  ["/assets?q=设备", "/assets?q=设备"],
  ["https://evil.example", "/home"],
  ["//evil", "/home"],
  ["/%5cevil", "/home"],
  ["/auth/error?reason=x", "/home"],
])("安全登录目标 %s", (input, target) => {
  const url = new URL(loginUrl(input), "http://localhost");
  expect(url.pathname).toBe("/bff/v1/auth/login");
  expect(url.searchParams.get("return_to")).toBe(target);
});
it("保留 JSON 错误中的安全诊断字段", async () => {
  const trace = "a".repeat(32);
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            code: "upstream.unavailable",
            message: "身份服务暂时不可用",
            trace_id: trace,
          }),
          { status: 502 },
        ),
    ),
  );
  await expect(loadMe()).rejects.toMatchObject({
    status: 502,
    error: { code: "upstream.unavailable", trace_id: trace },
  });
});
