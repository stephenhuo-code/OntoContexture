import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { hit, openAssets, page, stubAssets, summary } from "./assets-fixtures";

afterEach(() => vi.unstubAllGlobals());

type Call = { method: string; path: string; body?: unknown };
type SearchBody = {
  filters: Record<string, { values: string[]; includeNone: boolean }>;
  sort: { field: string; order: string };
  page: number;
  pageSize: number;
  keyword: string;
  browsePath: unknown[];
};

const tierOptions = {
  dimension: "tier",
  supportsNone: true,
  options: [
    { value: "tier.tier1", label: "tier.tier1", count: 3 },
    { value: "tier.tier2", label: "tier.tier2", count: 2 },
  ],
};

function setup(total = 40) {
  const calls = stubAssets([
    { method: "POST", path: "/bff/v1/assets/browse", body: { nodes: [] } },
    {
      method: "POST",
      path: "/bff/v1/assets/search",
      body: page([hit()], total),
    },
    {
      method: "POST",
      path: "/bff/v1/assets/type-counts",
      body: {
        counts: [{ entityType: "table", count: 1 }],
        topHitType: "table",
        defaultType: "table",
      },
    },
    { method: "POST", path: "/bff/v1/assets/facets", body: tierOptions },
    { path: /\/bff\/v1\/assets\/suggestions/, body: { groups: [] } },
    { path: /\/bff\/v1\/assets\/summary\//, body: summary },
  ]);
  return () => calls;
}

const lastSearch = (calls: Call[]) =>
  calls.filter((c) => c.path === "/bff/v1/assets/search").at(-1)
    ?.body as SearchBody;

it("快速筛选维度与 OM 一致；选中表类型时增加 5 个维度（FR-008）", async () => {
  setup();
  openAssets();
  const bar = await screen.findByRole("group", { name: "快速筛选" });
  expect(
    within(bar)
      .getAllByRole("button")
      .map((b) => b.textContent),
  ).toEqual([
    "资产类型",
    "业务域",
    "数据产品",
    "负责人",
    "分类标签",
    "分级（Tier）",
    "服务",
    "服务类型",
    "认证",
  ]);
  await screen.findByRole("option", { name: "数据表" });
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "搜索范围" }),
    "数据表",
  );
  await waitFor(() =>
    expect(
      within(bar)
        .getAllByRole("button")
        .map((b) => b.textContent)
        .slice(9),
    ).toEqual(["库", "Schema", "列", "表类型", "列描述"]),
  );
});

it("同维度多选为或、可选「无」且「无」不显示计数；选项计数来自 OM 聚合；可在选项中搜索（FR-008）", async () => {
  const calls = setup();
  openAssets();
  const bar = await screen.findByRole("group", { name: "快速筛选" });
  await userEvent.click(
    within(bar).getByRole("button", { name: "分级（Tier）" }),
  );
  const menu = await screen.findByRole("dialog", { name: "分级（Tier）选项" });
  const none = within(menu).getByRole("checkbox", { name: "无" });
  expect(none.closest("label")).toHaveTextContent(/^无$/);
  expect(
    within(menu).getByRole("checkbox", { name: "tier.tier1 3" }),
  ).toBeVisible();
  await userEvent.click(
    within(menu).getByRole("checkbox", { name: "tier.tier1 3" }),
  );
  await userEvent.click(
    within(menu).getByRole("checkbox", { name: "tier.tier2 2" }),
  );
  await waitFor(() =>
    expect(lastSearch(calls()).filters.tier).toEqual({
      values: ["tier.tier1", "tier.tier2"],
      includeNone: false,
    }),
  );
  await userEvent.click(none);
  await waitFor(() =>
    expect(lastSearch(calls()).filters.tier?.includeNone).toBe(true),
  );
  await userEvent.type(
    within(menu).getByRole("searchbox", { name: "搜索选项" }),
    "tier1",
  );
  await waitFor(() =>
    expect(
      calls().some(
        (c) =>
          c.path === "/bff/v1/assets/facets" &&
          (c.body as { optionQuery?: string }).optionQuery === "tier1",
      ),
    ).toBe(true),
  );
  await userEvent.click(within(bar).getByRole("button", { name: "服务" }));
  const svc = await screen.findByRole("dialog", { name: "服务选项" });
  expect(
    within(svc).queryByRole("checkbox", { name: "无" }),
  ).not.toBeInTheDocument();
});

it("条件条：筛选值可单独删除；清除全部回到无关键词的浏览状态；无条件时显示提示（FR-009、US2 场景 5）", async () => {
  const calls = setup();
  openAssets();
  const chips = await screen.findByRole("region", { name: "条件条" });
  expect(chips).toHaveTextContent(
    "提示：点击左侧浏览树节点可按层级筛选位置（不跳转页面），也可使用上方搜索框或快速筛选组合过滤资产。",
  );
  await userEvent.click(
    within(await screen.findByRole("group", { name: "快速筛选" })).getByRole(
      "button",
      { name: "分级（Tier）" },
    ),
  );
  const menu = await screen.findByRole("dialog", { name: "分级（Tier）选项" });
  await userEvent.click(
    within(menu).getByRole("checkbox", { name: "tier.tier1 3" }),
  );
  await userEvent.click(
    within(menu).getByRole("checkbox", { name: "tier.tier2 2" }),
  );
  await userEvent.type(
    screen.getByRole("searchbox", { name: "搜索数据资产" }),
    "工单{Enter}",
  );
  await userEvent.click(
    within(chips).getByRole("button", {
      name: "移除 分级（Tier）：tier.tier1",
    }),
  );
  await waitFor(() =>
    expect(lastSearch(calls()).filters.tier?.values).toEqual(["tier.tier2"]),
  );
  await userEvent.click(
    within(chips).getByRole("button", { name: "清除全部" }),
  );
  await waitFor(() => {
    const last = lastSearch(calls());
    expect(last.keyword).toBe("");
    expect(last.filters).toEqual({});
    expect(last.browsePath).toEqual([]);
  });
  expect(screen.getByRole("searchbox", { name: "搜索数据资产" })).toHaveValue(
    "",
  );
});

it("排序：热度（默认）、名称、相关性、最近更新，可切换升降序；改变排序回到第 1 页（FR-010）", async () => {
  const calls = setup();
  openAssets();
  const sort = await screen.findByRole("combobox", { name: "排序" });
  expect(
    within(sort)
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["热度", "名称", "相关性", "最近更新"]);
  expect(sort).toHaveValue("popularity");
  await userEvent.click(await screen.findByRole("button", { name: "下一页" }));
  await waitFor(() => expect(lastSearch(calls()).page).toBe(2));
  await userEvent.selectOptions(sort, "名称");
  await waitFor(() =>
    expect(lastSearch(calls())).toMatchObject({
      sort: { field: "name", order: "desc" },
      page: 1,
    }),
  );
  await userEvent.click(screen.getByRole("button", { name: "降序" }));
  await waitFor(() => expect(lastSearch(calls()).sort.order).toBe("asc"));
});

it("分页：每页 15 / 25 / 50 条，页头显示真实总数；超过 10000 条时提示缩小条件（FR-010、research R6）", async () => {
  const calls = setup(25000);
  openAssets();
  const size = await screen.findByRole("combobox", { name: "每页条数" });
  expect(
    within(size)
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["15", "25", "50"]);
  expect(await screen.findByText("共 25000 条")).toBeVisible();
  expect(screen.getByText("仅显示前 10000 条，请缩小条件")).toBeVisible();
  await userEvent.selectOptions(size, "50");
  await waitFor(() =>
    expect(lastSearch(calls())).toMatchObject({ pageSize: 50, page: 1 }),
  );
  expect(screen.getByText(/第 1 \/ 200 页/)).toBeVisible();
});
