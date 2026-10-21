// 最终演示第 1–2 步（登录、看到“设备”定义与列表）与第 5 步（直接调 bff：无令牌 401、受众不符 403）
import { expect, type Page, test } from "@playwright/test";

async function keycloakLogin(page: Page, username: string, password: string) {
  // 负责人的 realm 为两步登录（先用户名，再密码）；单步登录页同样适用
  await page.locator("#username").fill(username);
  const password$ = page.locator("#password");
  if (!(await password$.isVisible())) {
    await page
      .locator("input[type=submit], button[type=submit]")
      .first()
      .click();
  }
  await password$.fill(password);
  await page.locator("input[type=submit], button[type=submit]").first().click();
}

test("第 1–2 步：登录后看到设备的定义与列表", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/protocol\/openid-connect\/auth|login-actions/);
  await keycloakLogin(page, "user1", "user1");

  await expect(page).toHaveURL(/\/objects\/equipment$/);
  await expect(page.getByText("租户 local")).toBeVisible();
  await expect(page.getByRole("heading", { name: /设备/ })).toBeVisible();

  const definition = page.getByRole("table", { name: "对象定义" });
  await expect(
    definition.getByText("urn:ctx:object:quality:Equipment"),
  ).toBeVisible();
  await expect(definition.getByRole("row")).toHaveCount(6); // 表头 + 5 个属性

  const list = page.getByRole("table", { name: "对象列表" });
  await expect(list.getByRole("row")).toHaveCount(11); // 表头 + 10 台设备
  await expect(
    list.getByText("urn:ctx:obj:local:Equipment:CNC-01"),
  ).toBeVisible();

  // 浏览器只持有会话 Cookie，没有令牌
  const cookies = await page.context().cookies("http://localhost:8080");
  expect(cookies.map((c) => c.name)).toEqual(["ctx_session"]);
  expect(cookies[0]?.httpOnly).toBe(true);

  await page.getByRole("button", { name: "退出" }).click();
  await expect(page.getByRole("button", { name: "登录" })).toBeVisible();
});

test("第 5 步：无令牌直接调 bff 返回 401", async ({ request }) => {
  const resp = await request.get("/bff/v1/object-types/equipment/objects");
  expect(resp.status()).toBe(401);
  expect((await resp.json()).code).toBe("auth.invalid_token");
});

test("第 5 步：受众不符的令牌直接调 bff 返回 403", async ({ request }) => {
  const token = process.env.CTX_WRONG_AUDIENCE_TOKEN;
  test.skip(!token, "由 make e2e 提供（受众为 AI 网关、不含 bff 的令牌）");
  const resp = await request.get("/bff/v1/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(resp.status()).toBe(403);
  expect((await resp.json()).code).toBe("auth.invalid_audience");
});
