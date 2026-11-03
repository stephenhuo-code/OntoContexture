import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../App";
import * as api from "../api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function open(path = "/home") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response("{}", { status: 401 })),
  );
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
it("匿名页采用确认的浅蓝品牌布局，只提供企业认证入口", async () => {
  open();
  expect(
    await screen.findByRole("heading", { name: "欢迎登录织境" }),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: /构建企业AI Ready数据/ }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "使用企业账号登录" }),
  ).toBeEnabled();
  expect(screen.queryByLabelText("密码")).not.toBeInTheDocument();
  expect(
    screen.queryByText(/设计提案|设计预览|演示数据/),
  ).not.toBeInTheDocument();
  expect(screen.getByText("连接三域数据资产")).toBeVisible();
});
it("登录沿用 BFF 安全目标，没有自建密码提交", async () => {
  const login = vi.spyOn(api, "login").mockImplementation(() => {});
  open("/assets?q=equipment");
  await userEvent.click(
    await screen.findByRole("button", { name: "使用企业账号登录" }),
  );
  expect(login).toHaveBeenCalledWith("/assets?q=equipment");
});
it("管理员帮助可用键盘打开并关闭，不展示虚构联系方式", async () => {
  open();
  await screen.findByRole("heading", { name: "欢迎登录织境" });
  const help = screen.getByRole("button", { name: "联系管理员" });
  help.focus();
  await userEvent.keyboard("{Enter}");
  expect(
    await screen.findByRole("dialog", { name: "联系企业管理员" }),
  ).toBeVisible();
  expect(screen.getByText(/请勿向任何人发送你的密码/)).toBeVisible();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(help).toHaveFocus();
});
it("公共失败恢复页也复用品牌布局且不请求身份", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  render(
    <MemoryRouter
      initialEntries={["/auth/error?reason=cancelled&code=PRIVATE"]}
    >
      <App />
    </MemoryRouter>,
  );
  expect(
    screen.getByRole("heading", { name: /构建企业AI Ready数据/ }),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "登录已取消" })).toBeVisible();
  expect(screen.getByRole("link", { name: "重新登录" })).toHaveAttribute(
    "href",
    "/bff/v1/auth/login?return_to=%2Fhome",
  );
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.queryByText("PRIVATE")).not.toBeInTheDocument();
});
