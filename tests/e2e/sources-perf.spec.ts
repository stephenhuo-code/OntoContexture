import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { login } from "./helpers/login";

// 005 T078 实测（真实环境：浏览器 → Envoy → BFF → OM / Airflow）。默认不运行；CTX_PERF=1 时执行。
// 自带准备与清理：经 BFF 接入 MES、测量测试连接与“保存到首采完成”耗时，再测列表与目录读取 p95，最后删除。
const SERVICE = "perf-mes";
const N = 20;

test.skip(!process.env.CTX_PERF, "仅在 CTX_PERF=1 时测量");
test.beforeAll(() => cleanup());
test.afterAll(() => cleanup());

function cleanup() {
  execFileSync("uv", ["run", "python", "tests/e2e/om_cleanup.py", SERVICE], {
    stdio: "inherit",
  });
}

function password(): string {
  const b64 = execFileSync("kubectl", [
    "-n",
    "mock-sources",
    "get",
    "secret",
    "mock-readonly",
    "-o",
    "jsonpath={.data.mes-meta-ro}",
  ]).toString();
  return Buffer.from(b64, "base64").toString();
}

async function call(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(
    async ([m, p, b]) => {
      const r = await fetch(p as string, {
        method: m as string,
        credentials: "same-origin",
        cache: "no-store",
        headers: b ? { "Content-Type": "application/json" } : {},
        body: b ? JSON.stringify(b) : undefined,
      });
      return { status: r.status, body: await r.text() };
    },
    [method, path, body] as const,
  );
}

async function timings(page: Page, path: string): Promise<number[]> {
  return page.evaluate(
    async ([p, n]) => {
      const out: number[] = [];
      for (let i = 0; i < (n as number); i++) {
        const t0 = performance.now();
        const r = await fetch(p as string, {
          credentials: "same-origin",
          cache: "no-store",
        });
        await r.text();
        if (!r.ok) throw new Error(`${p} → ${r.status}`);
        out.push(performance.now() - t0);
      }
      return out;
    },
    [path, N] as const,
  );
}

const sorted = (xs: number[]) => [...xs].sort((a, b) => a - b);
const p95 = (xs: number[]) => sorted(xs)[Math.ceil(xs.length * 0.95) - 1]!;
const median = (xs: number[]) => sorted(xs)[Math.floor(xs.length / 2)]!;

test("T078：测试连接、保存到首采完成、列表与目录读取 p95", async ({ page }) => {
  test.setTimeout(600_000);
  await login(page, "engineer1", "/assets/sources");
  const connection = {
    hostPort: "mock-mes.mock-sources.svc:3306",
    username: "mes_meta_ro",
    password: password(),
    database: "mes",
    tls: false,
  };
  const report: Record<string, string> = {};

  // 测试连接：发起到 OM workflow 结束
  let t0 = Date.now();
  const started = await call(page, "POST", "/bff/v1/sources/test-connection", {
    serviceType: "Mysql",
    connection,
  });
  expect(started.status, started.body).toBe(202);
  const workflowId = JSON.parse(started.body).workflowId as string;
  await expect
    .poll(
      async () =>
        JSON.parse(
          (
            await call(
              page,
              "GET",
              `/bff/v1/sources/test-connection/${workflowId}`,
            )
          ).body,
        ).status,
      { timeout: 120_000, intervals: [1000] },
    )
    .toBe("Successful");
  report["测试连接"] = `${((Date.now() - t0) / 1000).toFixed(1)} s`;

  // 保存（创建服务与任务并部署）→ 立即运行 → 首采成功
  t0 = Date.now();
  const created = await call(page, "POST", "/bff/v1/sources", {
    name: SERVICE,
    displayName: SERVICE,
    serviceType: "Mysql",
    connection,
    scope: { includeViews: true },
    metadataSchedule: { cron: null },
    createLineageTask: false,
  });
  expect(created.status, created.body).toBe(201);
  const saved = Date.now();
  const trig = await call(
    page,
    "POST",
    `/bff/v1/sources/${SERVICE}/pipelines/metadata/trigger`,
  );
  expect(trig.status, trig.body).toBe(202);
  await expect
    .poll(
      async () =>
        JSON.parse(
          (
            await call(
              page,
              "GET",
              `/bff/v1/sources/${SERVICE}/pipelines/metadata/runs`,
            )
          ).body,
        ).data?.[0]?.pipelineState,
      { timeout: 300_000, intervals: [2000] },
    )
    .toBe("success");
  report["保存配置（创建并部署）"] = `${((saved - t0) / 1000).toFixed(1)} s`;
  report["保存到首采成功（含部署稳定等待）"] =
    `${((Date.now() - t0) / 1000).toFixed(1)} s`;

  const enc = encodeURIComponent;
  const targets: [string, string][] = [
    ["数据源列表 GET /assets/sources", "/bff/v1/sources"],
    ["数据源详情 GET /assets/sources/{name}", `/bff/v1/sources/${SERVICE}`],
    ["目录·服务", `/bff/v1/catalog/databaseService/${SERVICE}`],
    ["目录·数据库", `/bff/v1/catalog/database/${enc(`${SERVICE}.default`)}`],
    [
      "目录·Schema",
      `/bff/v1/catalog/databaseSchema/${enc(`${SERVICE}.default.mes`)}`,
    ],
  ];
  for (const [name, path] of targets) {
    const xs = await timings(page, path);
    report[name] =
      `p95 ${p95(xs).toFixed(0)} ms（中位 ${median(xs).toFixed(0)} ms，n=${N}）`;
  }
  console.log(JSON.stringify(report, null, 2));
});
