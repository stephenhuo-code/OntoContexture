import { screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { openShell, stubIdentity } from "./shell-test-utils";
afterEach(() => vi.unstubAllGlobals());
it("开发示例复用单一外壳，展示组件变体但不增加业务入口", async () => {
  stubIdentity();
  await openShell("/__dev/ui");
  expect(
    screen.getByRole("heading", { name: "组件与状态示例", level: 1 }),
  ).toBeVisible();
  expect(screen.getAllByRole("navigation", { name: "一级导航" })).toHaveLength(
    1,
  );
  expect(await screen.findByText("演示数据，仅用于开发验收")).toBeVisible();
  expect(screen.getByRole("button", { name: "主按钮" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "次按钮" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "禁用按钮" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "处理中" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "长中文输入示例" })).toBeVisible();
  expect(
    screen.queryByRole("link", { name: /组件与状态/ }),
  ).not.toBeInTheDocument();
});
it("五类状态可触发、结束和恢复，错误重试失败后仍能恢复", async () => {
  stubIdentity();
  await openShell("/__dev/ui");
  const example = within(
    await screen.findByRole("region", { name: "公共状态演示" }),
  );
  await userEvent.click(example.getByRole("button", { name: "加载示例" }));
  expect(example.getByRole("status")).toHaveAttribute("aria-busy", "true");
  await userEvent.click(example.getByRole("button", { name: "结束加载" }));
  expect(example.getByText("演示内容已加载")).toBeVisible();
  await userEvent.click(example.getByRole("button", { name: "空内容示例" }));
  expect(example.getByText("暂无演示内容")).toBeVisible();
  await userEvent.click(example.getByRole("button", { name: "加载演示内容" }));
  expect(example.getByText("演示内容已加载")).toBeVisible();
  await userEvent.click(
    example.getByRole("checkbox", { name: "重试仍然失败" }),
  );
  await userEvent.click(example.getByRole("button", { name: "错误示例" }));
  await userEvent.click(example.getByRole("button", { name: "重试" }));
  await waitFor(() =>
    expect(example.getByRole("button", { name: "重试" })).toBeEnabled(),
  );
  expect(example.getByText("演示请求失败")).toBeVisible();
  await userEvent.click(
    example.getByRole("checkbox", { name: "重试仍然失败" }),
  );
  await userEvent.click(example.getByRole("button", { name: "重试" }));
  expect(await example.findByText("演示内容已加载")).toBeVisible();
  for (const [button, title] of [
    ["无权限示例", "无权查看演示内容"],
    ["未开放示例", "演示功能尚未开放"],
  ]) {
    await userEvent.click(example.getByRole("button", { name: button }));
    expect(example.getByText(title)).toBeVisible();
    expect(
      example.queryByRole("button", { name: "重试" }),
    ).not.toBeInTheDocument();
  }
});
it("独立页面接入示例复用公共状态且不重复身份请求", async () => {
  const paths = stubIdentity();
  await openShell("/__dev/ui");
  const sample = within(
    await screen.findByRole("region", { name: "独立页面接入演示" }),
  );
  expect(sample.getByText("暂无示例记录")).toBeVisible();
  await userEvent.click(sample.getByRole("button", { name: "添加演示记录" }));
  expect(sample.getByText("演示记录：页面已接入统一外壳")).toBeVisible();
  expect(paths).toEqual(["/bff/v1/me"]);
});
it("开发示例仍然要求真实身份边界", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("{}", { status: 401 })),
  );
  const { render } = await import("@testing-library/react");
  const { MemoryRouter } = await import("react-router");
  const { App } = await import("../App");
  render(
    <MemoryRouter initialEntries={["/__dev/ui"]}>
      <App />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole("button", { name: "使用企业账号登录" }),
  ).toBeVisible();
  expect(
    screen.queryByText("演示数据，仅用于开发验收"),
  ).not.toBeInTheDocument();
});
