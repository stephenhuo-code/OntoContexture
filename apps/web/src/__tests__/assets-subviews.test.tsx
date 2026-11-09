import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import {
  TABLE_FQN,
  hit,
  openAssets,
  page,
  stubAssets,
  summary,
} from "./assets-fixtures";

afterEach(() => vi.unstubAllGlobals());

type Call = { method: string; path: string; body?: unknown };

function setup() {
  return stubAssets([
    { method: "POST", path: "/bff/v1/assets/browse", body: { nodes: [] } },
    { method: "POST", path: "/bff/v1/assets/search", body: page([hit()]) },
    {
      method: "POST",
      path: "/bff/v1/assets/type-counts",
      body: {
        counts: [{ entityType: "table", count: 1 }],
        topHitType: "table",
        defaultType: "table",
      },
    },
    {
      method: "POST",
      path: "/bff/v1/assets/facets",
      body: { dimension: "tier", supportsNone: true, options: [] },
    },
    { path: /\/bff\/v1\/assets\/suggestions/, body: { groups: [] } },
    { path: /\/bff\/v1\/assets\/summary\//, body: summary },
    {
      path: /\/bff\/v1\/catalog\//,
      status: 404,
      body: {
        code: "catalog.not_found",
        message: "目录中不存在",
        trace_id: "",
      },
    },
    {
      path: "/bff/v1/governance/options",
      body: {
        users: [],
        teams: [],
        domains: [],
        dataProducts: [],
        classifications: [],
        glossaryTerms: [],
      },
    },
  ]);
}

it("页头「数据源管理」进入 /assets/sources，「添加数据源」打开接入向导（US3 场景 1）", async () => {
  setup();
  openAssets();
  await userEvent.click(
    await screen.findByRole("link", { name: "数据源管理" }),
  );
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(
    /^\/assets\/sources$/,
  );
  expect(
    await screen.findByText("数据源管理", {
      selector: ".asset-breadcrumb strong",
    }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("link", { name: "数据资产" }));
  await userEvent.click(
    await screen.findByRole("link", { name: "添加数据源" }),
  );
  expect(
    await screen.findByRole("dialog", { name: "添加数据源" }),
  ).toBeVisible();
});

it("进入表详情后从面包屑返回，关键词、筛选与页码保持不变（US3 场景 2、FR-015）", async () => {
  const calls: Call[] = setup();
  openAssets();
  await userEvent.type(
    await screen.findByRole("searchbox", { name: "搜索数据资产" }),
    "工单{Enter}",
  );
  const list = await screen.findByRole("list", { name: "搜索结果" });
  await userEvent.click(within(list).getByRole("link", { name: "生产工单" }));
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(
    `/assets/table/${TABLE_FQN}`,
  );
  const crumb = document.querySelector(".asset-breadcrumb")!;
  expect(crumb).toHaveTextContent("数据资产/devtest-mes/work_order");
  await userEvent.click(
    within(crumb as HTMLElement).getByRole("link", { name: "数据资产" }),
  );
  expect(screen.getByRole("searchbox", { name: "搜索数据资产" })).toHaveValue(
    "工单",
  );
  await waitFor(() => {
    const last = calls.filter((c) => c.path === "/bff/v1/assets/search").at(-1)
      ?.body as { keyword: string };
    expect(last.keyword).toBe("工单");
  });
});
