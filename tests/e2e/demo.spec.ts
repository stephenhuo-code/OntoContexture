// 最终演示第 1–2 步（登录、看到“设备”定义与列表）与第 5 步（直接调 bff：无令牌 401、受众不符 403）
import { expect, test } from "@playwright/test";
import { APP_ORIGIN, login } from "./helpers/login";

test("第 1–2 步：登录后看到设备的定义与列表", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: /你好/ })).toBeVisible();
  await page.goto("/objects/equipment");
  await page.getByLabel(/当前账号/).click();
  await expect(page.getByText("租户：local")).toBeVisible();
  await page.getByLabel(/当前账号/).click();
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
  const cookies = await page.context().cookies(APP_ORIGIN);
  expect(cookies.map((c) => c.name)).toEqual(["ctx_session"]);
  expect(cookies[0]?.httpOnly).toBe(true);

  await page.getByRole("button", { name: "退出" }).click();
  await expect(
    page.getByRole("button", { name: "使用企业账号登录" }),
  ).toBeVisible();
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
