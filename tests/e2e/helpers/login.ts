import { expect, type Page } from "@playwright/test";
export const APP_ORIGIN = "http://localhost:8080";

export async function keycloakLogin(
  page: Page,
  username: string,
  password = username,
) {
  await expect(
    page.locator("#username:visible, #password:visible").first(),
  ).toBeVisible();
  const usernameField = page.locator("#username");
  if (await usernameField.isVisible()) {
    if (await usernameField.isEditable()) await usernameField.fill(username);
    else await expect(usernameField).toHaveValue(username);
  }
  const passwordField = page.locator("#password");
  if (!(await passwordField.isVisible()))
    await page
      .locator("input[type=submit],button[type=submit]")
      .first()
      .click();
  await passwordField.fill(password);
  await page.locator("input[type=submit],button[type=submit]").first().click();
}

/** 同一 BrowserContext 经已注册的 8080 回调登录；不导出 Cookie 或 token。 */
export async function login(
  page: Page,
  username = "engineer1",
  target = "/home",
) {
  await page.goto(APP_ORIGIN + target);
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toBeVisible();
  const me = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === "/bff/v1/me" &&
      [200, 403].includes(r.status()),
  );
  await page
    .getByRole("button", { name: "使用企业账号登录", exact: true })
    .click();
  await keycloakLogin(page, username);
  const response = await me;
  await page.waitForURL(
    (url) => url.origin === APP_ORIGIN && !url.pathname.startsWith("/bff/"),
  );
  return response;
}
