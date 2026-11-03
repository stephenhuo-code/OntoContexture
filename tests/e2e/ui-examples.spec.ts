import { expect, test } from "@playwright/test";
import { login } from "./helpers/login";
test("真实身份访问开发示例，状态恢复及长中文布局", async ({ page }) => {
  await login(page);
  await page.goto("http://localhost:5173/__dev/ui");
  await expect(
    page.getByRole("heading", { name: "组件与状态示例", level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole("navigation", { name: "一级导航" })).toHaveCount(
    1,
  );
  const example = page.getByRole("region", { name: "公共状态演示" });
  await example.getByRole("button", { name: "加载示例" }).click();
  await expect(example.getByRole("status")).toHaveAttribute(
    "aria-busy",
    "true",
  );
  await example.getByRole("button", { name: "结束加载" }).click();
  await expect(example.getByText("演示内容已加载")).toBeVisible();
  await example.getByRole("button", { name: "错误示例" }).click();
  await example.getByRole("checkbox", { name: "重试仍然失败" }).check();
  await example.getByRole("button", { name: "重试", exact: true }).click();
  await expect(
    example.getByRole("button", { name: "重试", exact: true }),
  ).toBeEnabled();
  await expect(example.getByText("演示请求失败")).toBeVisible();
  await example.getByRole("checkbox", { name: "重试仍然失败" }).uncheck();
  await example.getByRole("button", { name: "重试", exact: true }).click();
  await expect(example.getByText("演示内容已加载")).toBeVisible();
  for (const [button, title] of [
    ["空内容示例", "暂无演示内容"],
    ["无权限示例", "无权查看演示内容"],
    ["未开放示例", "演示功能尚未开放"],
  ]) {
    await example.getByRole("button", { name: button }).click();
    await expect(example.getByText(title)).toBeVisible();
  }
  const sample = page.getByRole("region", { name: "独立页面接入演示" });
  await sample.getByRole("button", { name: "添加演示记录" }).click();
  await expect(sample.getByText("演示记录：页面已接入统一外壳")).toBeVisible();
  await page
    .getByRole("textbox", { name: "长中文输入示例" })
    .fill("长中文输入与焦点验证".repeat(50));
  for (const size of [
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(size);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "退出", exact: true }).focus();
    await expect(
      page.getByRole("button", { name: "退出", exact: true }),
    ).toBeInViewport();
    await page.screenshot({
      path: test.info().outputPath(`ui-${size.width}.png`),
      fullPage: true,
    });
  }
});
