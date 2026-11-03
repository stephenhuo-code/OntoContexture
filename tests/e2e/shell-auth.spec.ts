import { expect, test } from "@playwright/test";
import { APP_ORIGIN, keycloakLogin, login } from "./helpers/login";

test("保留 SSO 的退出后登录仍需密码，错误密码不能进入，刷新保持登录", async ({
  page,
}) => {
  await login(page);
  const oldCookie = (await page.context().cookies(APP_ORIGIN)).find(
    (c) => c.name === "ctx_session",
  );
  await page.reload();
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "使用企业账号登录", exact: true })
    .click();
  await expect(page.locator("#password")).toBeVisible();
  await keycloakLogin(page, "engineer1", "incorrect-test-password");
  await expect(page.locator("#password")).toBeVisible();
  expect((await page.request.get(APP_ORIGIN + "/bff/v1/me")).status()).toBe(
    401,
  );
  await keycloakLogin(page, "engineer1");
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  const newCookie = (await page.context().cookies(APP_ORIGIN)).find(
    (c) => c.name === "ctx_session",
  );
  expect(Boolean(newCookie?.value)).toBe(true);
  expect(newCookie?.value === oldCookie?.value).toBe(false);
  expect(
    (
      await page.request.get(APP_ORIGIN + "/bff/v1/me", {
        headers: { Cookie: `ctx_session=${oldCookie?.value}` },
      })
    ).status(),
  ).toBe(401);
  await page.reload();
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
});

test("真实登录、账号、本地退出和旧 Cookie 失效", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  const cookie = (await page.context().cookies(APP_ORIGIN)).find(
    (c) => c.name === "ctx_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  await page.goto(APP_ORIGIN + "/home?history=1");
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toBeVisible();
  const denied = await page.request.get(APP_ORIGIN + "/bff/v1/me", {
    headers: { Cookie: `ctx_session=${cookie?.value}` },
  });
  expect(denied.status()).toBe(401);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toBeVisible();
});

test("仅业务用户被拒绝且能退出", async ({ page }) => {
  expect((await login(page, "user1")).status()).toBe(403);
  await expect(
    page.getByRole("heading", { name: "无权访问织境" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录", exact: true }),
  ).toBeVisible();
});

test("取消回调回到安全恢复页，重新登录生成新请求", async ({ page }) => {
  const initial = await page.request.get(
    APP_ORIGIN + "/bff/v1/auth/login?return_to=%2Fhome",
    { maxRedirects: 0 },
  );
  expect(initial.status()).toBe(302);
  const state = new URL(initial.headers().location).searchParams.get("state");
  await page.goto(
    APP_ORIGIN +
      `/bff/v1/auth/callback?error=access_denied&state=${encodeURIComponent(state ?? "")}&error_description=PRIVATE`,
  );
  await expect(page.getByRole("heading", { name: "登录已取消" })).toBeVisible();
  expect(page.url()).not.toContain("PRIVATE");
  const next = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === "/bff/v1/auth/login" && r.status() === 302,
  );
  await page.getByRole("link", { name: "重新登录" }).click();
  const nextState = new URL((await next).headers().location).searchParams.get(
    "state",
  );
  expect(nextState === state).toBe(false);
  await keycloakLogin(page, "engineer1");
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
});

test("无效回调不显示敏感内容", async ({ page }) => {
  await page.goto(
    APP_ORIGIN +
      "/bff/v1/auth/callback?code=PRIVATE&state=invalid&return_to=https%3A%2F%2Fevil",
  );
  await expect(page).toHaveURL(/\/auth\/error\?/);
  await expect(page.getByRole("heading", { name: "登录未完成" })).toBeVisible();
  await expect(page.getByText("PRIVATE", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "返回首页" })).toHaveAttribute(
    "href",
    "/home",
  );
});
