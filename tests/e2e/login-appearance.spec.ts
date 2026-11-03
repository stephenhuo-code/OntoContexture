import { expect, test } from "@playwright/test";
import { APP_ORIGIN, keycloakLogin } from "./helpers/login";

for (const size of [
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
]) {
  test(`正式浅蓝登录与企业认证 ${size.width}×${size.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(size);
    await page.goto(APP_ORIGIN + "/home");
    await expect(
      page.getByRole("heading", { name: "欢迎登录织境" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /构建企业AI Ready数据/ }),
    ).toBeVisible();
    await expect(page.getByText(/设计提案|设计预览|演示数据/)).toHaveCount(0);
    const card = page.getByRole("region", { name: "登录工作空间" });
    expect(
      await card.evaluate((el) => getComputedStyle(el).backgroundColor),
    ).toMatch(/255/);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const help = page.getByRole("button", { name: "联系管理员", exact: true });
    await help.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(help).toBeFocused();
    await page.screenshot({
      path: test.info().outputPath("entry.png"),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "使用企业账号登录", exact: true })
      .click();
    await expect(page.locator(".oc-identity--auth")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /构建企业AI Ready数据/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "验证你的企业身份" }),
    ).toBeVisible();
    if (!(await page.locator("#password").isVisible())) {
      await expect(
        page.getByText("请输入企业账号，继续验证身份。"),
      ).toBeVisible();
      await page.locator("#username").fill("engineer1");
      await page
        .locator("input[type=submit],button[type=submit]")
        .first()
        .click();
    }
    await expect(page.locator("#password")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /构建企业AI Ready数据/ }),
    ).toBeVisible();
    const identityHelp = page.getByRole("button", {
      name: "联系管理员",
      exact: true,
    });
    await identityHelp.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await expect(identityHelp).toBeFocused();
    await page.locator("#password").fill("preview-only");
    const visibility = page.getByRole("button", {
      name: "显示密码",
      exact: true,
    });
    await visibility.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#password")).toHaveAttribute("type", "text");
    await page.getByRole("button", { name: "隐藏密码", exact: true }).click();
    await page.locator("#password").fill("");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: test.info().outputPath("identity.png"),
      fullPage: true,
    });
    await keycloakLogin(page, "engineer1");
    await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  });
}
