import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { openShell, stubIdentity } from "./shell-test-utils";

afterEach(() => vi.unstubAllGlobals());
it("身份重新核验期间仍保留本次使用的菜单偏好", async () => {
  stubIdentity();
  await openShell();
  await userEvent.click(screen.getByRole("button", { name: "收起二级菜单" }));
  let release: (response: Response) => void = () => {};
  vi.mocked(fetch).mockImplementationOnce(
    () =>
      new Promise<Response>((resolve) => {
        release = resolve;
      }),
  );
  fireEvent.focus(window);
  await screen.findByText("正在确认身份");
  release(
    new Response(
      JSON.stringify({
        tenant_id: "local",
        user_id: "subject-1",
        display_name: "真实工程师",
        roles: ["ai-engineer"],
      }),
      { status: 200 },
    ),
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "展开二级菜单" })).toBeVisible(),
  );
});
it("四入口顺序、名称、品牌与首页二级准确，设备和开发页不入导航", async () => {
  stubIdentity();
  await openShell();
  const nav = screen.getByRole("navigation", { name: "一级导航" });
  expect(
    within(nav)
      .getAllByRole("link")
      .map((e) => e.getAttribute("aria-label")),
  ).toEqual(["新建对话", "首页", "资产", "Agent 工作台"]);
  expect(screen.getByRole("link", { name: "织境" })).toHaveAttribute(
    "href",
    "/home",
  );
  expect(within(nav).getByRole("link", { name: "首页" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  const secondary = screen.getByRole("navigation", { name: "首页导航" });
  expect(
    within(secondary)
      .getAllByRole("link")
      .map((e) => e.textContent),
  ).toEqual(["概览", "审批中心"]);
  expect(within(secondary).getByRole("link", { name: "概览" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.queryByRole("link", { name: /设备|组件示例/ }),
  ).not.toBeInTheDocument();
});
it.each([
  ["/home", "概览", "首页"],
  ["/home/", "概览", "首页"],
  ["/approvals", "审批中心", "首页"],
  ["/assets", "资产搜索", "资产"],
  ["/assets/", "资产搜索", "资产"],
  ["/agents", "Agent 工作台", "Agent 工作台"],
  ["/agents/new", "新建对话", "新建对话"],
])("深链 %s 的标题和选中入口一致", async (path, title, current) => {
  stubIdentity();
  await openShell(path);
  expect(screen.getByRole("heading", { name: title, level: 1 })).toBeVisible();
  const nav = screen.getByRole("navigation", { name: "一级导航" });
  expect(within(nav).getByRole("link", { name: current })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  expect(screen.queryByRole("navigation", { name: "首页导航" }) !== null).toBe(
    ["/home", "/home/", "/approvals"].includes(path),
  );
});
it("切页保留收起偏好，重复展开操作稳定，重新挂载默认展开", async () => {
  stubIdentity();
  const first = await openShell();
  await userEvent.click(screen.getByRole("button", { name: "收起二级菜单" }));
  expect(
    screen.queryByRole("navigation", { name: "首页导航" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("link", { name: "资产" }));
  await userEvent.click(screen.getByRole("link", { name: "首页" }));
  expect(
    screen.queryByRole("navigation", { name: "首页导航" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "展开二级菜单" }));
  await userEvent.click(screen.getByRole("button", { name: "收起二级菜单" }));
  first.unmount();
  await openShell();
  expect(screen.getByRole("navigation", { name: "首页导航" })).toBeVisible();
});
it("首页二级、历史前后与未知路径可恢复", async () => {
  stubIdentity();
  await openShell("/home", true);
  await userEvent.click(screen.getByRole("link", { name: "审批中心" }));
  expect(
    screen.getByRole("heading", { name: "审批中心", level: 1 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "测试后退" }));
  expect(screen.getByRole("heading", { name: "概览", level: 1 })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "测试前进" }));
  expect(screen.getByRole("link", { name: "审批中心" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
it.each(["/unknown/path", "/objects/a/b"])(
  "未知地址 %s 保留导航并可返回首页",
  async (path) => {
    stubIdentity();
    await openShell(path);
    expect(
      screen.getByRole("heading", { name: "页面不存在", level: 1 }),
    ).toBeVisible();
    expect(screen.getByRole("navigation", { name: "一级导航" })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "返回首页" }));
    expect(
      screen.getByRole("heading", { name: "概览", level: 1 }),
    ).toBeVisible();
  },
);

// 005：资产工作空间：二级为“资产搜索（未开放）”与“数据源”；不显示“数据接入”分组标题（负责人 2026-11-08 验收反馈）
it("资产工作空间的二级导航含数据源入口，指向 /sources", async () => {
  stubIdentity();
  await openShell("/assets");
  const secondary = screen.getByRole("navigation", { name: "数据资产导航" });
  const links = within(secondary).getAllByRole("link");
  expect(links.map((e) => e.textContent)).toEqual(["资产搜索", "数据源"]);
  expect(screen.queryByText("数据接入")).not.toBeInTheDocument();
  expect(
    within(secondary).getByRole("link", { name: "数据源" }),
  ).toHaveAttribute("href", "/sources");
  const nav = screen.getByRole("navigation", { name: "一级导航" });
  expect(within(nav).getByRole("link", { name: "资产" })).toHaveAttribute(
    "href",
    "/sources",
  );
});

it("一级与二级导航每个入口带对应图标（2026-11-08 负责人按附图调整配色与图标）", async () => {
  stubIdentity();
  await openShell("/assets");
  const nav = screen.getByRole("navigation", { name: "一级导航" });
  expect(
    within(nav)
      .getAllByRole("link")
      .map((a) => a.querySelector("svg")?.getAttribute("data-icon")),
  ).toEqual(["new", "home", "assets", "agents"]);
  const secondary = screen.getByRole("navigation", { name: "数据资产导航" });
  expect(
    within(secondary)
      .getAllByRole("link")
      .map((a) => a.querySelector("svg")?.getAttribute("data-icon")),
  ).toEqual(["search", "database"]);
  expect(
    document.querySelector(".module-label svg")?.getAttribute("data-icon"),
  ).toBe("module-asset");
});
