import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { login } from "./helpers/login";

// 005 端到端（真实环境：make up、make mock-data）。断言基于 003 金标准与 viewlab 标准答案，不基于原型示例值。
const SERVICE = "e2e-mes";

function secret(ns: string, name: string, key: string): string {
  const b64 = execFileSync("kubectl", ["-n", ns, "get", "secret", name, "-o", `jsonpath={.data.${key}}`]).toString();
  return Buffer.from(b64, "base64").toString();
}

async function bff(page: Page, method: string, path: string) {
  return page.evaluate(
    async ([m, p]) => {
      const r = await fetch(p as string, { method: m as string, credentials: "same-origin" });
      return { status: r.status, body: await r.text() };
    },
    [method, path],
  );
}

async function removeService(name: string) {
  // 清理经集群内 OM（admin1 删除）；与被测路径无关
  execFileSync("uv", ["run", "python", "tests/e2e/om_cleanup.py", name], { stdio: "inherit" });
}

test.describe.configure({ mode: "serial" });

test.beforeAll(() => removeService(SERVICE));
test.afterAll(() => removeService(SERVICE));

test("US1：接入 MES 并首采，统计等于 003 金标准，响应无明文密码", async ({ page }) => {
  test.setTimeout(300_000);
  const password = secret("mock-sources", "mock-readonly", "mes-meta-ro");
  await login(page, "engineer1", "/sources");
  await expect(page.getByRole("heading", { name: "数据源", level: 1 })).toBeVisible();
  const bodies: string[] = [];
  page.on("response", async (r) => {
    if (new URL(r.url()).pathname.startsWith("/bff/v1/sources")) bodies.push(await r.text().catch(() => ""));
  });

  await page.getByRole("button", { name: "添加数据源" }).click();
  const dialog = page.getByRole("dialog", { name: "添加数据源" });
  await dialog.getByLabel("显示名称 *").fill("E2E MES");
  await dialog.getByLabel("服务标识 *").fill(SERVICE);
  await dialog.getByRole("button", { name: /MySQL/ }).click();
  await dialog.getByRole("button", { name: "下一步" }).click();
  await dialog.getByLabel("主机地址 *").fill("mock-mes.mock-sources.svc");
  await dialog.getByLabel("数据库（选填）").fill("mes");
  await dialog.getByLabel("用户名 *").fill("mes_meta_ro");
  await dialog.getByLabel("密码 *").fill(password);
  await dialog.getByRole("button", { name: "测试连接" }).click();
  const steps = dialog.getByRole("table", { name: "连接检查步骤" });
  await expect(steps).toBeVisible({ timeout: 60_000 });
  for (const name of ["CheckAccess", "GetSchemas", "GetTables"])
    await expect(steps.getByRole("row", { name: new RegExp(name) })).toContainText("通过");
  await dialog.getByRole("button", { name: "下一步" }).click();
  await dialog.getByRole("button", { name: "下一步" }).click();
  await dialog.getByLabel("元数据采集 · 调度方式").selectOption("manual");
  await dialog.getByRole("button", { name: "保存配置" }).click();
  await expect(dialog).toBeHidden({ timeout: 60_000 });

  await expect(page).toHaveURL(new RegExp(`/sources/${SERVICE}`));
  await page.getByRole("tab", { name: "采集任务" }).click();
  await page.getByRole("link", { name: /e2e_mes_metadata_/ }).click();
  await page.getByRole("button", { name: "立即运行" }).click();
  await expect(page.getByRole("table", { name: "运行记录" }).getByText("成功")).toBeVisible({ timeout: 240_000 });

  await page.getByRole("tab", { name: "概览" }).click();
  await expect(page.locator(".metric", { hasText: "已采集表" })).toContainText("13");
  await expect(page.locator(".metric", { hasText: "字段元数据" })).toContainText("79");
  for (const b of bodies) expect(b).not.toContain(password);
  const detail = await bff(page, "GET", `/bff/v1/sources/${SERVICE}`);
  expect(detail.body).not.toContain(password);
});
