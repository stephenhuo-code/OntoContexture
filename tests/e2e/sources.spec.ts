import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { login } from "./helpers/login";

// 005 端到端（真实环境：make up、make mock-data）。断言基于 003 金标准与 viewlab 标准答案，不基于原型示例值。
const SERVICE = "e2e-mes";

function secret(ns: string, name: string, key: string): string {
  const b64 = execFileSync("kubectl", [
    "-n",
    ns,
    "get",
    "secret",
    name,
    "-o",
    `jsonpath={.data.${key}}`,
  ]).toString();
  return Buffer.from(b64, "base64").toString();
}

async function bff(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(
    async ([m, p, b]) => {
      const r = await fetch(p as string, {
        method: m as string,
        credentials: "same-origin",
        headers: b ? { "Content-Type": "application/json" } : {},
        body: b ? JSON.stringify(b) : undefined,
      });
      return { status: r.status, body: await r.text() };
    },
    [method, path, body] as const,
  );
}

async function removeService(name: string) {
  // 清理经集群内 OM（admin1 删除）；与被测路径无关
  execFileSync("uv", ["run", "python", "tests/e2e/om_cleanup.py", name], {
    stdio: "inherit",
  });
}

test.describe.configure({ mode: "serial" });

const OTHERS = ["e2e-qms", "e2e-dw"];
test.beforeAll(() => [SERVICE, ...OTHERS].forEach(removeService));
test.afterAll(() => [SERVICE, ...OTHERS].forEach(removeService));

test("US1：接入 MES 并首采，统计等于 003 金标准，响应无明文密码", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const password = secret("mock-sources", "mock-readonly", "mes-meta-ro");
  await login(page, "engineer1", "/sources");
  await expect(
    page.getByRole("heading", { name: "数据源", level: 1 }),
  ).toBeVisible();
  const bodies: string[] = [];
  page.on("response", async (r) => {
    if (new URL(r.url()).pathname.startsWith("/bff/v1/sources"))
      bodies.push(await r.text().catch(() => ""));
  });

  await page.getByRole("button", { name: "添加数据源" }).click();
  const dialog = page.getByRole("dialog", { name: "添加数据源" });
  await dialog.getByLabel("显示名称 *").fill("E2E MES");
  await dialog.getByLabel("服务标识 *").fill(SERVICE);
  await dialog.getByRole("button", { name: /MySQL/ }).click();
  await dialog.getByRole("button", { name: "下一步" }).click();
  await dialog.getByLabel("主机地址 *").fill("mock-mes.mock-sources.svc");
  await dialog.getByLabel("数据库（选填）").fill("mes");
  await dialog.getByLabel("用户名 *").fill("mes_meta_ro");
  await dialog.getByLabel("密码 *").fill(password);
  await dialog.getByRole("button", { name: "测试连接" }).click();
  const steps = dialog.getByRole("table", { name: "连接检查步骤" });
  await expect(steps).toBeVisible({ timeout: 60_000 });
  for (const name of ["CheckAccess", "GetSchemas", "GetTables"])
    await expect(
      steps.getByRole("row", { name: new RegExp(name) }),
    ).toContainText("通过");
  await dialog.getByRole("button", { name: "下一步" }).click();
  await dialog.getByRole("button", { name: "下一步" }).click();
  await dialog.getByLabel("元数据采集 · 调度方式").selectOption("manual");
  await dialog.getByRole("button", { name: "保存配置" }).click();
  await expect(dialog).toBeHidden({ timeout: 60_000 });

  await expect(page).toHaveURL(new RegExp(`/sources/${SERVICE}`));
  await page.getByRole("tab", { name: "采集任务" }).click();
  await page.getByRole("button", { name: /e2e_mes_metadata_/ }).click();
  await page.getByRole("button", { name: "立即运行" }).click();
  await expect(
    page.getByRole("table", { name: "运行记录" }).getByText("成功"),
  ).toBeVisible({ timeout: 240_000 });

  await page.getByRole("tab", { name: "概览" }).click();
  await expect(page.locator(".metric", { hasText: "已采集表" })).toContainText(
    "13",
  );
  await expect(
    page.locator(".metric", { hasText: "字段元数据" }),
  ).toContainText("79");
  for (const b of bodies) expect(b).not.toContain(password);
  const detail = await bff(page, "GET", `/bff/v1/sources/${SERVICE}`);
  expect(detail.body).not.toContain(password);
});

test("US2：手动任务的配置调度入口、运行详情步骤统计与最近一次日志、调度详情", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await login(page, "engineer1", `/sources/${SERVICE}?tab=tasks&task=metadata`);
  const runs = page.getByRole("table", { name: "运行记录" });
  await expect(runs.getByRole("row")).toHaveCount(2); // 表头 + US1 的那次运行
  await page.getByRole("button", { name: "配置调度" }).click();
  await expect(
    page.getByRole("tab", { name: "采集配置", selected: true }),
  ).toBeVisible();
  await page.goto(`/sources/${SERVICE}?tab=tasks&task=metadata`);
  await runs.getByRole("button", { name: "查看运行" }).first().click();
  const dialog = page.getByRole("dialog", { name: "运行详情" });
  const steps = dialog.getByRole("table", { name: "步骤统计" });
  await expect(steps.getByRole("row", { name: /Mysql/ })).toBeVisible();
  await expect(steps.getByRole("row", { name: /OpenMetadata/ })).toBeVisible();
  await expect(dialog.getByLabel("运行日志")).not.toBeEmpty();
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("button", { name: "调度详情" }).click();
  await expect(page.getByRole("dialog", { name: "调度任务" })).toContainText(
    /e2e_mes_metadata_/,
  );
});

test("US3：MES / QMS / Doris 四层目录浏览、面包屑与表结构", async ({
  page,
}) => {
  test.setTimeout(420_000);
  await login(page, "engineer1", "/sources");
  // QMS、Doris 经 BFF 接口接入并首采（US1 的界面流程已在上面覆盖）
  const sources = [
    {
      name: "e2e-qms",
      serviceType: "Postgres",
      connection: {
        hostPort: "mock-qms-rw.mock-sources.svc:5432",
        username: "qms_meta_ro",
        password: secret("mock-sources", "mock-readonly", "qms-meta-ro"),
        database: "qms",
        tls: false,
      },
      scope: {
        includeViews: true,
        schemaFilterPattern: { includes: ["^public$"], excludes: [] },
      },
    },
    {
      name: "e2e-dw",
      serviceType: "Doris",
      connection: {
        hostPort: "doris-fe-service.contexture.svc:9030",
        username: "mock_dw_reader",
        password: secret("mock-sources", "mock-dw-reader", "password"),
        database: "mock_dw",
        tls: false,
      },
      scope: { includeViews: true },
    },
  ];
  for (const s of sources) {
    const created = await bff(page, "POST", "/bff/v1/sources", {
      ...s,
      displayName: s.name,
      metadataSchedule: { cron: null },
      createLineageTask: false,
    });
    expect(created.status, created.body).toBe(201);
    const t = await bff(
      page,
      "POST",
      `/bff/v1/sources/${s.name}/pipelines/metadata/trigger`,
    );
    expect(t.status, t.body).toBe(202);
  }
  for (const s of sources)
    await expect
      .poll(
        async () =>
          JSON.parse(
            (
              await bff(
                page,
                "GET",
                `/bff/v1/sources/${s.name}/pipelines/metadata/runs`,
              )
            ).body,
          ).data?.[0]?.pipelineState,
        { timeout: 300_000, intervals: [3000] },
      )
      .toBe("success");

  // MES：已采集元数据页签 → 数据库 → Schema → 表（MySQL 为 default → 物理库 → 表）
  await page.goto(`/sources/${SERVICE}?tab=metadata`);
  await page
    .getByRole("table", { name: "数据库目录" })
    .getByRole("link", { name: "default" })
    .click();
  await expect(page.getByText("METADATA CATALOG")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "资产层级" })).toHaveText(
    `${SERVICE}›default`,
  );
  await expect(page.getByRole("tab", { name: "采集任务" })).toHaveCount(0);
  await page
    .getByRole("table", { name: "Schema 列表" })
    .getByRole("link", { name: "mes" })
    .click();
  const tables = page.getByRole("table", { name: "数据表列表" });
  await expect(tables.getByRole("row")).toHaveCount(14); // 表头 + 13 张表（003 金标准）
  await tables.getByRole("link").first().click();
  await expect(page.getByRole("navigation", { name: "资产层级" })).toHaveText(
    new RegExp(`^${SERVICE}›default›mes›\\w+$`),
  );
  await expect(page.getByRole("region", { name: "结构信息" })).toContainText(
    "PRIMARY_KEY",
  );
  await expect(
    page.getByRole("table", { name: "字段元数据" }).getByText("PK").first(),
  ).toBeVisible();
  await page.getByRole("link", { name: "← 返回所属数据源" }).click();
  await expect(page).toHaveURL(new RegExp(`/sources/${SERVICE}$`));

  // QMS：左侧目录树（PostgreSQL 为 物理库 → public → 表）
  const tree = page.getByRole("navigation", { name: "数据源目录" });
  await expect(tree.getByRole("button", { name: /^e2e-qms/ })).toContainText(
    "7",
  );
  await tree.getByRole("button", { name: "展开 e2e-qms" }).click();
  await tree.getByRole("button", { name: "展开 qms" }).click();
  await tree.getByRole("button", { name: /^public/ }).click();
  await expect(page.getByRole("navigation", { name: "资产层级" })).toHaveText(
    "e2e-qms›qms›public",
  );
  await expect(
    page.getByRole("table", { name: "数据表列表" }).getByRole("row"),
  ).toHaveCount(8);

  // Doris：default → 物理库 → 表，键列按 OM 原生连接器标为主键
  await tree.getByRole("button", { name: "展开 e2e-dw" }).click();
  await tree.getByRole("button", { name: "展开 default" }).last().click();
  await tree.getByRole("button", { name: /^mock_dw/ }).click();
  await expect(page.getByRole("navigation", { name: "资产层级" })).toHaveText(
    "e2e-dw›default›mock_dw",
  );
  await expect(
    page.getByRole("table", { name: "数据表列表" }).getByRole("row"),
  ).toHaveCount(9);
});

test("US4：五层级编辑属性、保留周期继承与恢复、重新采集后保留", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const enc = encodeURIComponent;
  const save = async (dialogName: string) => {
    const dialog = page.getByRole("dialog", { name: dialogName });
    await dialog.getByRole("button", { name: "保存属性" }).click();
    await expect(dialog).toBeHidden();
  };
  const card = (name: string) => page.getByRole("region", { name });

  // 数据源：描述与 Tier
  await login(page, "engineer1", `/sources/${SERVICE}`);
  await card("数据源属性").getByRole("button", { name: "编辑属性" }).click();
  let dialog = page.getByRole("dialog", { name: "编辑数据源属性" });
  await dialog.getByLabel("描述").fill("E2E 服务说明");
  await dialog.getByLabel("重要程度（Tier）").selectOption("Tier.Tier2");
  await save("编辑数据源属性");
  await expect(card("数据源属性")).toContainText("E2E 服务说明");
  await expect(card("数据源属性")).toContainText("Tier.Tier2");

  // 数据库：保留周期
  await page.goto(
    `/sources/${SERVICE}/assets/database/${enc(`${SERVICE}.default`)}`,
  );
  await card("数据库属性").getByRole("button", { name: "编辑属性" }).click();
  await page
    .getByRole("dialog", { name: "编辑数据库属性" })
    .getByLabel("保留周期")
    .fill("P30D");
  await save("编辑数据库属性");
  await expect(card("数据库属性")).toContainText("P30D");

  // Schema：显示名称；保留周期继承自数据库
  await page.goto(
    `/sources/${SERVICE}/assets/databaseSchema/${enc(`${SERVICE}.default.mes`)}`,
  );
  await expect(card("Schema属性")).toContainText(
    `继承自 数据库 · ${SERVICE}.default`,
  );
  await card("Schema属性").getByRole("button", { name: "编辑属性" }).click();
  await page
    .getByRole("dialog", { name: "编辑Schema属性" })
    .getByLabel("显示名称")
    .fill("E2E 生产库");
  await save("编辑Schema属性");
  await expect(
    page.getByRole("heading", { level: 2, name: "E2E 生产库" }),
  ).toBeVisible();

  // 表：单独设置保留周期后清空，恢复继承；分类标签
  await page
    .getByRole("table", { name: "数据表列表" })
    .getByRole("link")
    .first()
    .click();
  const tableUrl = page.url();
  await expect(card("数据表属性")).toContainText(
    `继承自 数据库 · ${SERVICE}.default`,
  );
  await card("数据表属性").getByRole("button", { name: "编辑属性" }).click();
  dialog = page.getByRole("dialog", { name: "编辑数据表属性" });
  await dialog.getByLabel("显示名称").fill("E2E 表");
  await dialog.getByLabel("保留周期").fill("PT24H");
  await dialog.getByRole("checkbox", { name: "PII.Sensitive" }).check();
  await save("编辑数据表属性");
  await expect(card("数据表属性")).toContainText("PT24H");
  await expect(card("数据表属性")).toContainText("单独设置");
  await expect(card("数据表属性")).toContainText("PII.Sensitive");
  await card("数据表属性").getByRole("button", { name: "编辑属性" }).click();
  await page
    .getByRole("dialog", { name: "编辑数据表属性" })
    .getByLabel("保留周期")
    .fill("");
  await save("编辑数据表属性");
  await expect(card("数据表属性")).toContainText("P30D");
  await expect(card("数据表属性")).toContainText(
    `继承自 数据库 · ${SERVICE}.default`,
  );

  // 字段：描述
  const cols = page.getByRole("table", { name: "字段元数据" });
  await cols.getByRole("button", { name: "编辑属性" }).first().click();
  await page
    .getByRole("dialog", { name: "编辑字段属性" })
    .getByLabel("描述")
    .fill("E2E 字段说明");
  await save("编辑字段属性");
  await expect(cols).toContainText("E2E 字段说明");

  // 重新采集（overrideMetadata=false）后人工维护的属性保留；等待触发后的新运行成功（不是上一次运行）
  const runs = async () =>
    JSON.parse(
      (
        await bff(
          page,
          "GET",
          `/bff/v1/sources/${SERVICE}/pipelines/metadata/runs`,
        )
      ).body,
    ).data as { runId: string; pipelineState: string }[];
  const previous = (await runs())[0]?.runId;
  const t = await bff(
    page,
    "POST",
    `/bff/v1/sources/${SERVICE}/pipelines/metadata/trigger`,
  );
  expect(t.status, t.body).toBe(202);
  await expect
    .poll(
      async () => {
        const latest = (await runs())[0];
        return latest?.runId !== previous ? latest?.pipelineState : "old";
      },
      { timeout: 240_000, intervals: [3000] },
    )
    .toBe("success");
  await page.goto(tableUrl);
  await expect(
    page.getByRole("heading", { level: 2, name: "E2E 表" }),
  ).toBeVisible();
  await expect(card("数据表属性")).toContainText("PII.Sensitive");
  await expect(page.getByRole("table", { name: "字段元数据" })).toContainText(
    "E2E 字段说明",
  );
  await page.goto(`/sources/${SERVICE}`);
  await expect(card("数据源属性")).toContainText("E2E 服务说明");
});
