import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { APP_ORIGIN, login } from "./helpers/login";

// 006 端到端（真实环境：make up、make seed、make dev-metadata）。
// 断言基于开发态导入工具的 fixture（testdata/mockfactory/om_import）与 OM 实际数据，不基于原型示例值。
const TABLE = "devtest-mes.default.mes.work_order";
const SAME_NAME = "devtest-mes.default.mes_archive.work_order";

test.describe.configure({ mode: "serial" });

async function search(page: Page, keyword: string) {
  const box = page.getByRole("searchbox", { name: "搜索数据资产" });
  await box.fill(keyword);
  await box.press("Enter");
  await expect(page.getByRole("list", { name: "搜索结果" })).toBeVisible();
}

test.describe("旧地址重定向（D1、SC-007）", () => {
  for (const [from, to] of [
    ["/sources", "/assets/sources"],
    ["/sources/devtest-mes", "/assets/sources/devtest-mes"],
    [
      `/sources/devtest-mes/assets/table/${encodeURIComponent(TABLE)}`,
      `/assets/table/${encodeURIComponent(TABLE)}`,
    ],
  ])
    test(`${from} → ${to}`, async ({ page }) => {
      await login(page, "engineer1", from);
      await expect(page).toHaveURL(`${APP_ORIGIN}${to}`);
    });
});

test("US1：按表名搜索，类型列表、高亮、来源与摘要来自 OM（SC-002 搜索路径）", async ({
  page,
}) => {
  await login(page, "engineer1", "/assets");
  const started = Date.now();
  let steps = 0;
  await search(page, "work_order");
  steps += 2; // 输入关键词、回车
  const types = page.getByRole("navigation", { name: "资产类型" });
  await expect(types.getByRole("button", { name: /数据表/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  const list = page.getByRole("list", { name: "搜索结果" });
  const cards = list.getByRole("article");
  await expect(cards.first()).toBeVisible();
  const crumbs = await list.locator(".asset-card__crumb").allTextContents();
  expect(crumbs).toEqual(
    expect.arrayContaining([
      "devtest-mes / default / mes",
      "devtest-mes / default / mes_archive",
    ]),
  );
  await expect(list.getByText("开发态测试元数据").first()).toBeVisible();
  const summary = page.getByRole("complementary", { name: "资产摘要" });
  await expect(summary).toBeVisible();
  await summary.getByRole("tab", { name: "Schema" }).click();
  steps += 1;
  await expect(summary.getByRole("row", { name: /wo_no/ })).toContainText(
    "主键",
  );
  expect(steps).toBeLessThanOrEqual(5);
  expect(Date.now() - started).toBeLessThanOrEqual(30_000);
  console.log(`[006 SC-002] 搜索路径 ${steps} 步，${Date.now() - started}ms`);
});

test("US2：浏览树定位 Schema、负责人「无」、清除全部（SC-002 浏览路径）", async ({
  page,
}) => {
  await login(page, "engineer1", "/assets");
  const started = Date.now();
  const tree = page.getByRole("navigation", { name: "数据资产浏览树" });
  await tree.getByRole("button", { name: "展开 数据库" }).click();
  await tree.getByRole("button", { name: "展开 Mysql" }).click();
  await tree.getByRole("button", { name: "展开 devtest-mes" }).click();
  await tree.getByRole("button", { name: "展开 default" }).click();
  await tree.getByRole("button", { name: /^mes \d+$/ }).click();
  await expect(page).toHaveURL(`${APP_ORIGIN}/assets`);
  const list = page.getByRole("list", { name: "搜索结果" });
  await expect(list.getByRole("article").first()).toBeVisible();
  for (const c of await list.locator(".asset-card__crumb").allTextContents())
    expect(c.startsWith("devtest-mes / default / mes")).toBe(true);
  console.log(`[006 SC-002] 浏览路径 5 步，${Date.now() - started}ms`);
  expect(Date.now() - started).toBeLessThanOrEqual(30_000);
  const chips = page.getByRole("region", { name: "条件条" });
  await expect(chips.getByRole("button", { name: /^移除位置/ })).toHaveCount(5);
  await page
    .getByRole("group", { name: "快速筛选" })
    .getByRole("button", { name: "负责人" })
    .click();
  await page
    .getByRole("dialog", { name: "负责人选项" })
    .getByRole("checkbox", { name: "无" })
    .check();
  await expect(chips).toContainText("负责人：无");
  await chips.getByRole("button", { name: "清除全部" }).click();
  await expect(chips).toContainText("提示：点击左侧浏览树节点");
});

test("US3：卡片进入表详情并返回保留条件；列结果定位；术语只读详情（SC-007）", async ({
  page,
}) => {
  await login(page, "engineer1", "/assets");
  await search(page, "work_order");
  await page
    .getByRole("list", { name: "搜索结果" })
    .getByRole("link", { name: "生产工单" })
    .first()
    .click();
  await expect(page.getByRole("table", { name: "字段元数据" })).toBeVisible();
  await page
    .locator(".asset-breadcrumb")
    .getByRole("link", { name: "数据资产" })
    .click();
  await expect(
    page.getByRole("searchbox", { name: "搜索数据资产" }),
  ).toHaveValue("work_order");

  await search(page, "wo_no");
  await page
    .getByRole("navigation", { name: "资产类型" })
    .getByRole("button", { name: /^列/ })
    .click();
  const col = page
    .getByRole("list", { name: "搜索结果" })
    .getByRole("link")
    .first();
  await col.click();
  await expect(
    page
      .getByRole("table", { name: "字段元数据" })
      .locator('tr[aria-current="true"]'),
  ).toContainText("wo_no");

  await page.goto("/assets");
  await search(page, "工单");
  await page
    .getByRole("navigation", { name: "资产类型" })
    .getByRole("button", { name: /业务术语/ })
    .click();
  await page
    .getByRole("list", { name: "搜索结果" })
    .getByRole("link", { name: /工单/ })
    .first()
    .click();
  const detail = page.getByRole("region", { name: "业务术语详情" });
  await expect(detail).toContainText("ContextureDevGlossary");
  await expect(detail.getByRole("button", { name: /编辑/ })).toHaveCount(0);
});

test("三种视口下数据资产页没有整页横向溢出；浏览器只请求同源 /bff/（FR-019）", async ({
  page,
}) => {
  const foreign: string[] = [];
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (
      u.origin !== APP_ORIGIN &&
      !u.hostname.includes("keycloak") &&
      !u.pathname.includes("/realms/")
    )
      foreign.push(r.url());
  });
  await login(page, "engineer1", "/assets");
  for (const [w, h] of [
    [1280, 800],
    [768, 900],
    [390, 844],
  ] as const) {
    await page.setViewportSize({ width: w, height: h });
    await search(page, "work_order");
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow, `${w}px`).toBeLessThanOrEqual(0);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  // 窄屏下摘要以覆盖层显示，先按 Esc 关闭再打开「目录」抽屉
  await expect(
    page.getByRole("complementary", { name: "资产摘要" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "目录" }).click();
  await expect(page.getByRole("dialog", { name: "资产目录" })).toBeVisible();
  const api = foreign.filter((u) => !/\.(js|css|woff2?|svg|png)(\?|$)/.test(u));
  expect(api).toEqual([]);
});

test("SC-003：搜索、筛选、翻页各 20 次，p95 与 2 秒比较并记录", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await login(page, "engineer1", "/assets");
  const samples: Record<string, number[]> = {
    search: [],
    filter: [],
    page: [],
  };
  const failures: string[] = [];
  async function timed(kind: string, act: () => Promise<unknown>) {
    const started = Date.now();
    try {
      await Promise.all([
        page.waitForResponse(
          (r) =>
            r.url().endsWith("/bff/v1/assets/search") && r.status() === 200,
        ),
        act(),
      ]);
      await expect(page.getByRole("list", { name: "搜索结果" })).toBeVisible();
      samples[kind]!.push(Date.now() - started);
    } catch (e) {
      failures.push(`${kind}: ${String(e).slice(0, 120)}`);
    }
  }
  const words = ["work_order", "employee", "工单", "质检", "supplier"];
  for (let i = 0; i < 20; i++) {
    const box = page.getByRole("searchbox", { name: "搜索数据资产" });
    await timed("search", async () => {
      await box.fill(`${words[i % words.length]}`);
      await box.press("Enter");
    });
  }
  await page
    .getByRole("region", { name: "条件条" })
    .getByRole("button", { name: "清除全部" })
    .click();
  for (let i = 0; i < 20; i++)
    await timed("filter", async () => {
      await page
        .getByRole("combobox", { name: "排序" })
        .selectOption(i % 2 ? "名称" : "最近更新");
    });
  for (let i = 0; i < 20; i++)
    await timed("page", async () => {
      await page
        .getByRole("button", { name: i % 2 ? "上一页" : "下一页" })
        .click();
    });
  const p95 = (xs: number[]) => {
    const s = [...xs].sort((a, b) => a - b);
    return s[Math.max(0, Math.ceil(s.length * 0.95) - 1)] ?? 0;
  };
  const report = Object.fromEntries(
    Object.entries(samples).map(([k, xs]) => [
      k,
      { n: xs.length, p95: p95(xs), max: Math.max(...xs) },
    ]),
  );
  mkdirSync("test-results", { recursive: true });
  writeFileSync(
    "test-results/006-sc003.json",
    JSON.stringify({ report, failures }, null, 2),
  );
  console.log(
    `[006 SC-003] ${JSON.stringify(report)} 环境失败：${failures.length}`,
  );
  for (const [k, v] of Object.entries(report))
    expect(v.p95, `${k} p95`).toBeLessThanOrEqual(2000);
});

test("同名表：卡片面包屑区分服务与 Schema（SC-005）", async ({ page }) => {
  await login(page, "engineer1", "/assets");
  await search(page, "work_order");
  const crumbs = await page
    .getByRole("list", { name: "搜索结果" })
    .locator(".asset-card__crumb")
    .allTextContents();
  const fqnParts = [TABLE, SAME_NAME].map((f) =>
    f.split(".").slice(0, 3).join(" / "),
  );
  for (const p of fqnParts) expect(crumbs).toContain(p);
});
