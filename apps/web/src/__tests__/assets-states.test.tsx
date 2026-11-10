import { screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { openAssets, page, stubAssets } from "./assets-fixtures";

afterEach(() => vi.unstubAllGlobals());

const base = [
  { method: "POST", path: "/bff/v1/assets/browse", body: { nodes: [] } },
  {
    method: "POST",
    path: "/bff/v1/assets/type-counts",
    body: { counts: [], topHitType: null, defaultType: null },
  },
  { path: /\/bff\/v1\/assets\/suggestions/, body: { groups: [] } },
];

it("出错：显示真实错误码与重试入口，不显示任何示例数据（FR-015、SC-006）", async () => {
  stubAssets([
    ...base,
    {
      method: "POST",
      path: "/bff/v1/assets/search",
      status: 503,
      body: {
        code: "search.index_missing",
        message: "OpenMetadata 搜索索引缺失：Failed to find index x",
        trace_id: "a".repeat(32),
      },
    },
  ]);
  openAssets();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("search.index_missing");
  expect(alert).toHaveTextContent("OpenMetadata 搜索索引缺失");
  expect(within(alert).getByRole("button", { name: "重试" })).toBeVisible();
  expect(
    screen.queryByRole("list", { name: "搜索结果" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("article")).not.toBeInTheDocument();
});

it("零资产：显示空状态并说明可添加数据源或运行开发态导入（FR-015）", async () => {
  stubAssets([
    ...base,
    { method: "POST", path: "/bff/v1/assets/search", body: page([]) },
  ]);
  openAssets();
  expect(await screen.findByText("尚未接入任何数据资产")).toBeVisible();
  expect(screen.getByText(/添加数据源/, { selector: "p" })).toHaveTextContent(
    "make dev-metadata",
  );
  expect(screen.getByRole("link", { name: "添加数据源" })).toBeVisible();
});

it("加载中：请求未返回时显示加载状态，不显示旧结果", async () => {
  stubAssets(base);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const path = new URL(request.url, "http://localhost").pathname;
      if (path === "/bff/v1/me")
        return new Response(
          JSON.stringify({
            tenant_id: "local",
            user_id: "u",
            roles: ["ai-engineer"],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      return new Promise<Response>(() => undefined);
    }),
  );
  openAssets();
  expect(await screen.findByText("正在搜索")).toBeVisible();
  expect(
    screen.queryByRole("list", { name: "搜索结果" }),
  ).not.toBeInTheDocument();
});

// 窄屏摘要覆盖层由 tests/e2e/assets.spec.ts 在 390px 视口验证（覆盖层出现，按 Esc 关闭后才能打开「目录」抽屉）
