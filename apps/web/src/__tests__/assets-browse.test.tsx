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
type BrowseBody = { parentPath: { level: string; value: string }[] };
type SearchBody = {
  browsePath: { level: string; value: string }[];
  keyword: string;
};

const roots = {
  nodes: [
    {
      level: "root",
      value: "databases",
      label: "数据库",
      count: 43,
      hasChildren: true,
    },
  ],
};
const serviceTypes = {
  nodes: [
    {
      level: "serviceType",
      value: "mysql",
      label: "Mysql",
      count: 14,
      hasChildren: true,
    },
  ],
};
const services = {
  nodes: [
    {
      level: "service",
      value: "devtest-mes",
      label: "devtest-mes",
      count: 14,
      hasChildren: true,
    },
  ],
};

function browseRoute(calls: () => Call[]) {
  return {
    method: "POST",
    path: "/bff/v1/assets/browse",
    get body() {
      const last = calls()
        .filter((c) => c.path === "/bff/v1/assets/browse")
        .at(-1)?.body as BrowseBody | undefined;
      const depth = last?.parentPath.length ?? 0;
      return depth === 0 ? roots : depth === 1 ? serviceTypes : services;
    },
  };
}

function setup() {
  let calls: Call[] = [];
  calls = stubAssets([
    browseRoute(() => calls),
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
      body: { code: "catalog.not_found", message: "x", trace_id: "" },
    },
  ]);
  return () => calls;
}

const browseCalls = (calls: Call[]) =>
  calls
    .filter((c) => c.path === "/bff/v1/assets/browse")
    .map((c) => (c.body as BrowseBody).parentPath.length);

it("无关键词时左栏为带计数的浏览树；展开时才加载下层（FR-006）", async () => {
  const calls = setup();
  openAssets();
  const tree = await screen.findByRole("navigation", {
    name: "数据资产浏览树",
  });
  expect(
    await within(tree).findByRole("button", { name: "数据库 43" }),
  ).toBeVisible();
  expect(browseCalls(calls()).every((d) => d === 0)).toBe(true);
  await userEvent.click(
    within(tree).getByRole("button", { name: "展开 数据库" }),
  );
  expect(
    await within(tree).findByRole("button", { name: "Mysql 14" }),
  ).toBeVisible();
  expect(browseCalls(calls())).toContain(1);
});

it("点击节点只设置位置条件、不跳页；条件条逐层显示位置（FR-006、FR-009）", async () => {
  const calls = setup();
  openAssets();
  const tree = await screen.findByRole("navigation", {
    name: "数据资产浏览树",
  });
  await userEvent.click(
    await within(tree).findByRole("button", { name: "展开 数据库" }),
  );
  await userEvent.click(
    await within(tree).findByRole("button", { name: "展开 Mysql" }),
  );
  await userEvent.click(
    await within(tree).findByRole("button", { name: "devtest-mes 14" }),
  );
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(/^\/assets$/);
  await waitFor(() => {
    const last = calls()
      .filter((c) => c.path === "/bff/v1/assets/search")
      .at(-1)?.body as SearchBody;
    expect(last.browsePath.map((s) => `${s.level}:${s.value}`)).toEqual([
      "root:databases",
      "serviceType:mysql",
      "service:devtest-mes",
    ]);
  });
  const chips = screen.getByRole("region", { name: "条件条" });
  expect(
    within(chips)
      .getAllByRole("button", { name: /^移除位置/ })
      .map((b) => b.getAttribute("aria-label")),
  ).toEqual(["移除位置 数据库", "移除位置 Mysql", "移除位置 devtest-mes"]);
  await userEvent.click(
    within(chips).getByRole("button", { name: "移除位置 Mysql" }),
  );
  await waitFor(() => {
    const last = calls()
      .filter((c) => c.path === "/bff/v1/assets/search")
      .at(-1)?.body as SearchBody;
    expect(last.browsePath.map((s) => s.value)).toEqual(["databases"]);
  });
});

it("在子视图中点击浏览树节点回到探索视图并带上位置条件（FR-003、US3 场景 4）", async () => {
  const calls = setup();
  openAssets(`/assets/table/${encodeURIComponent(TABLE_FQN)}`);
  const tree = await screen.findByRole("navigation", {
    name: "数据资产浏览树",
  });
  await userEvent.click(
    await within(tree).findByRole("button", { name: "数据库 43" }),
  );
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(/^\/assets$/);
  await waitFor(() => {
    const last = calls()
      .filter((c) => c.path === "/bff/v1/assets/search")
      .at(-1)?.body as SearchBody;
    expect(last.browsePath.map((s) => s.value)).toEqual(["databases"]);
  });
});

it("窄屏「目录」按钮打开抽屉，抽屉内为浏览树", async () => {
  setup();
  openAssets();
  const toggle = await screen.findByRole("button", { name: "目录" });
  await userEvent.click(toggle);
  const drawer = screen.getByRole("dialog", { name: "资产目录" });
  expect(
    await within(drawer).findByRole("button", { name: "数据库 43" }),
  ).toBeVisible();
});
