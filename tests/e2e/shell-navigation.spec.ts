import { expect, test } from "@playwright/test";
import { login } from "./helpers/login";

for (const viewport of [
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
]) {
  test(`生产导航、历史、空间与键盘 ${viewport.width}×${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await login(page);
    const nav = page.getByRole("navigation", { name: "一级导航" });
    await expect(nav.getByRole("link")).toHaveCount(4);
    await expect(
      page.getByRole("heading", { name: "概览", level: 1 }),
    ).toBeVisible();
    await page.getByRole("link", { name: "审批中心", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "审批中心尚未开放" }),
    ).toBeVisible();
    const collapse = page.getByRole("button", { name: "收起二级菜单" });
    await collapse.focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("button", { name: "展开二级菜单" }),
    ).toBeVisible();
    // 005：一级“资产”进入数据源；二级“资产搜索”（006）尚未开放
    await nav.getByRole("link", { name: "资产" }).click();
    await expect(
      page.getByRole("heading", { name: "数据源", level: 1 }),
    ).toBeVisible();
    // 切页时保留收起状态；展开后进入二级“资产搜索”，再收起以延续后续断言
    const expand = page.getByRole("button", { name: "展开二级菜单" });
    await expect(expand).toBeVisible();
    await expand.click();
    await page
      .getByRole("navigation", { name: "数据资产导航" })
      .getByRole("link", { name: "资产搜索" })
      .click();
    await expect(
      page.getByRole("heading", { name: "资产搜索尚未开放" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "收起二级菜单" }).click();
    await page.goBack();
    await page.goBack();
    await expect(
      page.getByRole("heading", { name: "审批中心", level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "展开二级菜单" }),
    ).toBeVisible();
    await page.goForward();
    await page.goForward();
    await page.reload();
    await expect(nav.getByRole("link", { name: "资产" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    for (const title of ["Agent 工作台", "新建对话"]) {
      const link = nav.getByRole("link", { name: title });
      await link.focus();
      await expect(link).toBeFocused();
      expect(
        await link.evaluate((el) => getComputedStyle(el).outlineStyle),
      ).not.toBe("none");
      await expect(
        page.getByRole("tooltip", { name: title, exact: true }),
      ).toBeVisible();
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("heading", { name: `${title}尚未开放` }),
      ).toBeVisible();
      await expect(
        page.getByRole("navigation", { name: "首页导航" }),
      ).toHaveCount(0);
    }
    await page.getByRole("button", { name: "返回首页" }).click();
    await expect(
      page.getByRole("button", { name: "收起二级菜单" }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("navigation", { name: "首页导航" }),
    ).toBeVisible();
    await page.getByLabel(/当前账号：/).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText("租户：local", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "退出", exact: true }).focus();
    await expect(
      page.getByRole("button", { name: "退出", exact: true }),
    ).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: test.info().outputPath(`shell-${viewport.width}.png`),
      fullPage: true,
    });
  });
}
test("生产示例路由不存在，未知地址可恢复且占位不请求业务", async ({ page }) => {
  await login(page);
  const requests: string[] = [];
  page.on("request", (r) => {
    if (new URL(r.url()).pathname.startsWith("/bff/"))
      requests.push(new URL(r.url()).pathname);
  });
  for (const path of [
    "/__dev/ui",
    "/missing",
    "/assets",
    "/assets/",
    "/agents",
    "/agents/new",
    "/approvals",
  ]) {
    await page.goto(path);
    if (path === "/__dev/ui" || path === "/missing")
      await expect(
        page.getByRole("heading", { name: "页面不存在", level: 1 }),
      ).toBeVisible();
    else
      await expect(
        page.getByRole("heading", { name: /尚未开放/ }),
      ).toBeVisible();
    await expect(page.getByRole("link", { name: /设备|组件示例/ })).toHaveCount(
      0,
    );
    await page.getByRole("button", { name: "返回首页" }).click();
    await expect(
      page.getByRole("heading", { name: "概览", level: 1 }),
    ).toBeVisible();
  }
  expect(requests.every((p) => p === "/bff/v1/me")).toBe(true);
});

test("二级栏可用鼠标拖动调整宽度，刷新后保持（负责人 2026-11-08 反馈）", async ({
  page,
}) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("ctx.e2e.widthReset")) {
      localStorage.removeItem("ctx.secondaryWidth");
      sessionStorage.setItem("ctx.e2e.widthReset", "1");
    }
  });
  await login(page, "engineer1", "/sources");
  const sep = page.getByRole("separator", { name: "调整二级栏宽度" });
  const b = (await sep.boundingBox())!;
  await page.mouse.move(b.x + 3, b.y + 300);
  await page.mouse.down();
  await page.mouse.move(b.x + 123, b.y + 300, { steps: 6 });
  await page.mouse.up();
  await expect(sep).toHaveAttribute("aria-valuenow", "356");
  await page.reload();
  await expect(
    page.getByRole("separator", { name: "调整二级栏宽度" }),
  ).toHaveAttribute("aria-valuenow", "356");
});
