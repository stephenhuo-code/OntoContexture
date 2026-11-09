import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import {
  TABLE_FQN,
  hit,
  metricHit,
  openAssets,
  page,
  stubAssets,
  summary,
} from "./assets-fixtures";

afterEach(() => vi.unstubAllGlobals());

const counts = {
  counts: [
    { entityType: "tableColumn", count: 8 },
    { entityType: "table", count: 2 },
    { entityType: "metric", count: 1 },
  ],
  topHitType: "table",
  defaultType: "table",
};

function routes(
  searchBody: unknown = page([hit(), metricHit]),
  summaryBody: unknown = summary,
) {
  return [
    { method: "POST", path: "/bff/v1/assets/type-counts", body: counts },
    { method: "POST", path: "/bff/v1/assets/search", body: searchBody },
    { path: /\/bff\/v1\/assets\/suggestions/, body: { groups: [] } },
    { path: /\/bff\/v1\/assets\/summary\//, body: summaryBody },
  ];
}

async function search(keyword: string) {
  const box = await screen.findByRole("searchbox", { name: "搜索数据资产" });
  await userEvent.type(box, `${keyword}{Enter}`);
}

it("有关键词时左栏为类型列表，只列计数大于 0 的类型并默认选中首条命中类型；切换类型只刷新列表（FR-007）", async () => {
  const calls = stubAssets(routes());
  openAssets();
  await search("工单");
  const types = await screen.findByRole("navigation", { name: "资产类型" });
  const buttons = await within(types).findAllByRole("button");
  expect(buttons.map((b) => b.textContent)).toEqual([
    "列8",
    "数据表2",
    "指标1",
  ]);
  expect(within(types).getByRole("button", { name: /数据表/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await waitFor(() => {
    const last = calls.filter((c) => c.path === "/bff/v1/assets/search").at(-1)
      ?.body as { entityType: string };
    expect(last.entityType).toBe("table");
  });
  await userEvent.click(within(types).getByRole("button", { name: /列/ }));
  await waitFor(() => {
    const last = calls.filter((c) => c.path === "/bff/v1/assets/search").at(-1)
      ?.body as { entityType: string };
    expect(last.entityType).toBe("tableColumn");
  });
});

it("结果卡片：位置、名称链接、认证、高亮、业务域、负责人、分级（Tier）与数据安全级别分开、命中统计、来源（FR-011、FR-014）", async () => {
  stubAssets(routes());
  openAssets();
  await search("工单");
  const list = await screen.findByRole("list", { name: "搜索结果" });
  const card = within(list).getByRole("article", { name: "生产工单" });
  expect(card).toHaveTextContent("devtest-mes / default / mes");
  expect(within(card).getByRole("link", { name: "生产工单" })).toHaveAttribute(
    "href",
    `/assets/table/${encodeURIComponent(TABLE_FQN)}`,
  );
  expect(within(card).getByText("工单", { selector: "mark" })).toBeVisible();
  expect(card).toHaveTextContent("认证Certification.Gold");
  expect(card).toHaveTextContent("业务域开发态-生产域");
  expect(card).toHaveTextContent("负责人admin");
  expect(card).toHaveTextContent("分级（Tier）Tier.Tier1");
  expect(card).toHaveTextContent("数据安全级别数据级别.二级");
  expect(card).toHaveTextContent("命中 3 处");
  expect(card).toHaveTextContent("开发态测试元数据");
  const metric = within(list).getByRole("article", { name: "产线良率" });
  expect(within(metric).queryByRole("link")).not.toBeInTheDocument();
  expect(metric).toHaveTextContent("真实采集来源");
});

it("结果更新后自动选中第一条并显示只读摘要：概览与 Schema 两个页签，Esc 关闭（FR-012）", async () => {
  const calls = stubAssets(routes());
  openAssets();
  await search("工单");
  const panel = await screen.findByRole("complementary", { name: "资产摘要" });
  await waitFor(() =>
    expect(
      calls.some((c) => c.path === `/bff/v1/assets/summary/table/${TABLE_FQN}`),
    ).toBe(true),
  );
  expect(
    within(panel)
      .getAllByRole("tab")
      .map((t) => t.textContent),
  ).toEqual(["概览", "Schema"]);
  const labels = within(panel)
    .getAllByRole("term")
    .map((t) => t.textContent);
  expect(labels).toEqual([
    "描述",
    "负责人",
    "业务域",
    "分级（Tier）",
    "数据安全级别",
    "认证",
    "业务术语",
    "分类标签",
    "数据产品",
    "来源",
  ]);
  expect(within(panel).getByRole("link", { name: "生产工单" })).toHaveAttribute(
    "href",
    `/assets/table/${encodeURIComponent(TABLE_FQN)}`,
  );
  await userEvent.click(within(panel).getByRole("tab", { name: "Schema" }));
  const row = within(panel).getByRole("row", { name: /wo_no/ });
  expect(row).toHaveTextContent("varchar(32)");
  expect(row).toHaveTextContent("主键");
  expect(row).toHaveTextContent("工单号");
  expect(row).toHaveTextContent("数据级别.一级");
  await userEvent.keyboard("{Escape}");
  expect(
    screen.queryByRole("complementary", { name: "资产摘要" }),
  ).not.toBeInTheDocument();
});

it("摘要返回的身份与所选资产不一致时显示错误，不串号", async () => {
  stubAssets(
    routes(page([hit()]), {
      ...summary,
      ref: { ...summary.ref, id: "other-id" },
    }),
  );
  openAssets();
  await search("工单");
  const panel = await screen.findByRole("complementary", { name: "资产摘要" });
  expect(await within(panel).findByRole("alert")).toHaveTextContent(
    "摘要与所选资产不一致",
  );
});

it("没有命中时显示无匹配结果并关闭摘要（US1 场景 7）", async () => {
  stubAssets([
    {
      method: "POST",
      path: "/bff/v1/assets/type-counts",
      body: { counts: [], topHitType: null, defaultType: null },
    },
    { method: "POST", path: "/bff/v1/assets/search", body: page([]) },
    { path: /\/bff\/v1\/assets\/suggestions/, body: { groups: [] } },
  ]);
  openAssets();
  await search("不存在的词");
  expect(await screen.findByText("无匹配结果")).toBeVisible();
  expect(screen.getByRole("button", { name: "清除条件" })).toBeVisible();
  expect(
    screen.queryByRole("complementary", { name: "资产摘要" }),
  ).not.toBeInTheDocument();
});

it("顶栏面包屑以「数据资产」开头，可点击返回探索视图", async () => {
  stubAssets(routes());
  openAssets();
  const h1 = await screen.findByRole("heading", { level: 1, name: "数据资产" });
  expect(within(h1).getByRole("link", { name: "数据资产" })).toHaveAttribute(
    "href",
    "/assets",
  );
  expect(
    await screen.findByRole("heading", { level: 2, name: "全部数据资产" }),
  ).toBeVisible();
  expect(await screen.findByText("共 2 条")).toBeVisible();
});
