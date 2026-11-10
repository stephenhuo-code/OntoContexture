import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { openShell, stubIdentity } from "./shell-test-utils";
afterEach(() => vi.unstubAllGlobals());
it("首页保留四项指标、待办及最近资产，无虚构数量和业务请求", async () => {
  const paths = stubIdentity();
  await openShell();
  expect(
    screen.getByRole("heading", { name: "你好，真实工程师" }),
  ).toBeVisible();
  for (const name of [
    "数据资产",
    "本体对象",
    "Agent 会话",
    "待处理审批",
    "我的待办",
    "最近浏览资产",
  ])
    expect(screen.getByRole("heading", { name })).toBeVisible();
  expect(screen.getAllByText("尚未接入")).toHaveLength(4);
  expect(
    screen.queryByText(/\b0\b|2026-|spec\s*00[4-8]|MES|engineer1/i),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "问 Agent" }),
  ).not.toBeInTheDocument();
  expect(paths).toEqual(["/bff/v1/me"]);
});
it.each([
  ["/agents", "Agent 工作台"],
  ["/agents/new", "新建对话"],
  ["/approvals", "审批中心"],
])("%s 明确未开放并可返回，不请求业务服务", async (path, title) => {
  const paths = stubIdentity();
  await openShell(path);
  expect(
    screen.getByRole("heading", { name: `${title}尚未开放` }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "重试" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "返回首页" }));
  expect(screen.getByRole("heading", { name: "概览", level: 1 })).toBeVisible();
  expect(paths).toEqual(["/bff/v1/me"]);
});
it("长中文身份保留完整问候和可用账号操作", async () => {
  const name = "非常长的中文账号名称".repeat(30);
  stubIdentity(name);
  await openShell();
  expect(screen.getByRole("heading", { name: `你好，${name}` })).toBeVisible();
  expect(screen.getByRole("button", { name: "退出" })).toBeEnabled();
});

// 006 FR-001：/assets 是统一的「数据资产」页面，不再显示「尚未开放」占位；D3：搜索框只在本页出现
it("/assets 显示数据资产页面而不是尚未开放", async () => {
  stubIdentity();
  await openShell("/assets");
  expect(
    screen.getByRole("heading", { name: "数据资产", level: 1 }),
  ).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: /尚未开放/ }),
  ).not.toBeInTheDocument();
});
