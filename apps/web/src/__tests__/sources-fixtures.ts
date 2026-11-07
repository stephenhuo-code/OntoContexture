// 005 组件测试夹具：模拟 BFF 响应（仅测试使用，不进入生产代码；断言基于这些夹具，不基于原型示例值）
import { vi } from "vitest";

export const T0 = Date.UTC(2026, 10, 7, 2, 0, 0);

export const sourcesFixture = [
  {
    name: "fixture-mes",
    displayName: "夹具 MES",
    serviceType: "Mysql",
    database: "mes",
    configured: true,
    tableCount: 13,
    columnCount: 79,
    pipelines: [
      {
        kind: "metadata",
        name: "fixture_mes_metadata_AbCd1234",
        fullyQualifiedName: "fixture-mes.fixture_mes_metadata_AbCd1234",
        deployed: true,
        schedule: { cron: "0 2 * * *" },
        scheduleEnabled: true,
        lastRun: {
          runId: "11111111-1111-4111-8111-111111111111",
          pipelineState: "success",
          startDate: T0,
          endDate: T0 + 25000,
          steps: [],
        },
      },
    ],
  },
  {
    name: "fixture-qms",
    displayName: "夹具 QMS",
    serviceType: "Postgres",
    database: "qms",
    configured: true,
    tableCount: 7,
    columnCount: 53,
    pipelines: [
      {
        kind: "metadata",
        name: "fixture_qms_metadata_EfGh5678",
        fullyQualifiedName: "fixture-qms.fixture_qms_metadata_EfGh5678",
        deployed: true,
        schedule: { cron: null },
        scheduleEnabled: false,
        lastRun: {
          runId: "22222222-2222-4222-8222-222222222222",
          pipelineState: "partialSuccess",
          startDate: T0,
          endDate: T0 + 5000,
          steps: [],
        },
      },
    ],
  },
  {
    name: "fixture-erp",
    displayName: "夹具 ERP",
    serviceType: "Oracle",
    database: "ERP",
    configured: false,
    tableCount: 0,
    columnCount: 0,
    pipelines: [],
  },
];

type Route = { method?: string; path: string | RegExp; status?: number; body: unknown };

/** 按方法与路径返回夹具；未匹配的请求返回 404，便于发现遗漏。 */
export function stubBff(routes: Route[]) {
  const calls: { method: string; path: string; body?: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const url = new URL(request.url, "http://localhost");
      const method = request.method;
      const text = method === "GET" ? "" : await request.clone().text();
      calls.push({ method, path: url.pathname, body: text ? JSON.parse(text) : undefined });
      const hit = routes.find(
        (r) =>
          (r.method ?? "GET") === method &&
          (typeof r.path === "string" ? r.path === url.pathname : r.path.test(url.pathname)),
      );
      if (!hit)
        return new Response(JSON.stringify({ code: "test.unmatched", message: url.pathname, trace_id: "" }), {
          status: 404,
        });
      return new Response(JSON.stringify(hit.body), {
        status: hit.status ?? 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}
