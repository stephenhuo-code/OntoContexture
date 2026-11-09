import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { renderQ } from "./query-wrapper";
import { afterEach, expect, it, vi } from "vitest";
import { AssetsWorkspace } from "../features/assets/AssetsWorkspace";
import { sourcesFixture, stubBff } from "./sources-fixtures";

afterEach(() => vi.unstubAllGlobals());

const WF = "33333333-3333-4333-8333-333333333333";
const okSteps = [
  { name: "CheckAccess", mandatory: true, passed: true },
  { name: "GetSchemas", mandatory: true, passed: true },
  { name: "GetTables", mandatory: true, passed: true },
  { name: "GetViews", mandatory: false, passed: true },
  {
    name: "GetQueries",
    mandatory: false,
    passed: false,
    message: "SELECT command denied",
  },
];

function open() {
  renderQ(
    <MemoryRouter initialEntries={["/assets/sources"]}>
      <Routes>
        <Route path="/assets/*" element={<AssetsWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function stepOne(
  name = "wms",
  service = "plant-wms",
  connector = "MySQL",
) {
  await userEvent.click(
    await screen.findByRole("button", { name: "添加数据源" }),
  );
  const dialog = screen.getByRole("dialog", { name: "添加数据源" });
  await userEvent.type(within(dialog).getByLabelText("显示名称 *"), name);
  await userEvent.type(within(dialog).getByLabelText("服务标识 *"), service);
  await userEvent.click(
    within(dialog).getByRole("button", { name: new RegExp(connector) }),
  );
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  return dialog;
}

it("服务标识规则与重复拦截", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: sourcesFixture } }]);
  open();
  let dialog = await stepOne("x", "Bad_Name");
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "服务标识需要 2–50 位",
  );
  await userEvent.clear(within(dialog).getByLabelText("服务标识 *"));
  await userEvent.type(
    within(dialog).getByLabelText("服务标识 *"),
    "fixture-mes",
  );
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent("服务标识已存在");
  dialog = screen.getByRole("dialog");
  expect(dialog).toBeVisible();
});

it("按连接器区分库字段与 TLS：MySQL 选填无 TLS，PostgreSQL 必填有 TLS", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: [] } }]);
  open();
  const dialog = await stepOne();
  expect(within(dialog).getByLabelText("数据库（选填）")).toBeVisible();
  expect(
    within(dialog).queryByLabelText("启用 TLS 加密连接"),
  ).not.toBeInTheDocument();
  await userEvent.click(within(dialog).getByRole("button", { name: "上一步" }));
  await userEvent.click(
    within(dialog).getByRole("button", { name: /PostgreSQL/ }),
  );
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  expect(within(dialog).getByLabelText("数据库 *")).toBeVisible();
  expect(within(dialog).getByLabelText("启用 TLS 加密连接")).toBeVisible();
});

it("测试连接逐步展示 OM 结果；参数变更后结果失效；必需步骤失败不能继续", async () => {
  const calls = stubBff([
    { path: "/bff/v1/sources", body: { data: [] } },
    {
      method: "POST",
      path: "/bff/v1/sources/test-connection",
      status: 202,
      body: { workflowId: WF, status: "Running", steps: [] },
    },
    {
      path: `/bff/v1/sources/test-connection/${WF}`,
      body: { workflowId: WF, status: "Successful", steps: okSteps },
    },
  ]);
  open();
  const dialog = await stepOne();
  await userEvent.type(within(dialog).getByLabelText("主机地址 *"), "wms.svc");
  await userEvent.type(within(dialog).getByLabelText("用户名 *"), "ro");
  await userEvent.type(within(dialog).getByLabelText("密码 *"), "pw");
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "请先完成连接测试",
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "测试连接" }),
  );
  const result = await within(dialog).findByRole("table", {
    name: "连接检查步骤",
  });
  expect(within(result).getAllByRole("row")).toHaveLength(6);
  expect(
    within(result).getByText("GetQueries").closest("tr"),
  ).toHaveTextContent("可选失败SELECT command denied");
  const sent = calls.find((c) => c.path === "/bff/v1/sources/test-connection");
  expect(sent?.body).toMatchObject({
    serviceType: "Mysql",
    connection: { hostPort: "wms.svc:3306", username: "ro", password: "pw" },
  });
  await userEvent.type(within(dialog).getByLabelText("用户名 *"), "x");
  expect(
    within(dialog).queryByRole("table", { name: "连接检查步骤" }),
  ).not.toBeInTheDocument();
});

it("过滤规则非法正则拦截；视图血缘任务需采集视图；按任务调度后保存", async () => {
  const calls = stubBff([
    { path: "/bff/v1/sources", body: { data: [] } },
    {
      method: "POST",
      path: "/bff/v1/sources/test-connection",
      status: 202,
      body: { workflowId: WF, status: "Successful", steps: okSteps },
    },
    {
      path: `/bff/v1/sources/test-connection/${WF}`,
      body: { workflowId: WF, status: "Successful", steps: okSteps },
    },
    {
      method: "POST",
      path: "/bff/v1/sources",
      status: 201,
      body: {
        ...sourcesFixture[0],
        connection: { hostPort: "x", username: "ro", password: "*********" },
        scope: {},
      },
    },
  ]);
  open();
  const dialog = await stepOne();
  await userEvent.type(within(dialog).getByLabelText("主机地址 *"), "wms.svc");
  await userEvent.type(within(dialog).getByLabelText("用户名 *"), "ro");
  await userEvent.type(within(dialog).getByLabelText("密码 *"), "pw");
  await userEvent.click(
    within(dialog).getByRole("button", { name: "测试连接" }),
  );
  await within(dialog).findByRole("table", { name: "连接检查步骤" });
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  // 第 3 步逐层说明（MySQL：数据库层固定为 default，Schema 为物理库）与写法规则
  expect(
    within(dialog).getByLabelText("数据库 · 包含"),
  ).toHaveAccessibleDescription(/固定为 default/);
  expect(
    within(dialog).getByLabelText("Schema · 包含"),
  ).toHaveAccessibleDescription(/物理库/);
  expect(dialog).toHaveTextContent(/从名称开头匹配/);
  await userEvent.click(within(dialog).getByLabelText("表 · 包含"));
  await userEvent.paste("([bad"); // type() 会把 [ 当作按键描述符
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "不是有效的正则表达式",
  );
  await userEvent.clear(within(dialog).getByLabelText("表 · 包含"));
  await userEvent.type(
    within(dialog).getByLabelText("表 · 包含"),
    "^po_.*, ^supplier$",
  );
  const lineage = within(dialog).getByLabelText(/创建视图血缘任务/);
  await userEvent.click(within(dialog).getByLabelText(/采集视图/));
  expect(lineage).toBeDisabled();
  await userEvent.click(within(dialog).getByLabelText(/采集视图/));
  await userEvent.click(lineage);
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  await userEvent.selectOptions(
    within(dialog).getByLabelText("视图血缘 · 调度方式"),
    "manual",
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存配置" }),
  );
  await waitFor(() =>
    expect(
      calls.some((c) => c.method === "POST" && c.path === "/bff/v1/sources"),
    ).toBe(true),
  );
  const saved = calls.find(
    (c) => c.method === "POST" && c.path === "/bff/v1/sources",
  );
  expect(saved?.body).toMatchObject({
    name: "plant-wms",
    serviceType: "Mysql",
    scope: {
      includeViews: true,
      tableFilterPattern: { includes: ["^po_.*", "^supplier$"], excludes: [] },
    },
    metadataSchedule: { cron: "0 2 * * *" },
    createLineageTask: true,
    lineageSchedule: { cron: null },
  });
});

it("保存失败显示真实错误", async () => {
  stubBff([
    { path: "/bff/v1/sources", body: { data: [] } },
    {
      method: "POST",
      path: "/bff/v1/sources/test-connection",
      status: 202,
      body: { workflowId: WF, status: "Successful", steps: okSteps },
    },
    {
      path: `/bff/v1/sources/test-connection/${WF}`,
      body: { workflowId: WF, status: "Successful", steps: okSteps },
    },
    {
      method: "POST",
      path: "/bff/v1/sources",
      status: 502,
      body: {
        code: "source.deploy_failed",
        message: "Failed to deploy Ingestion Pipeline",
        trace_id: "d".repeat(32),
      },
    },
  ]);
  open();
  const dialog = await stepOne();
  await userEvent.type(within(dialog).getByLabelText("主机地址 *"), "wms.svc");
  await userEvent.type(within(dialog).getByLabelText("用户名 *"), "ro");
  await userEvent.type(within(dialog).getByLabelText("密码 *"), "pw");
  await userEvent.click(
    within(dialog).getByRole("button", { name: "测试连接" }),
  );
  await within(dialog).findByRole("table", { name: "连接检查步骤" });
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  await userEvent.click(within(dialog).getByRole("button", { name: "下一步" }));
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存配置" }),
  );
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "Failed to deploy Ingestion Pipeline",
  );
});

it("连接器卡片显示缩写图标与连接器名称（按原型）", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: [] } }]);
  open();
  await userEvent.click(
    await screen.findByRole("button", { name: "添加数据源" }),
  );
  const dialog = screen.getByRole("dialog", { name: "添加数据源" });
  const cards = within(dialog)
    .getByRole("group", { name: "选择数据库连接器" })
    .querySelectorAll("button");
  expect(
    [...cards].map((c) => [
      c.querySelector(".connector-badge")?.textContent,
      c.querySelector("b")?.textContent,
      c.querySelector("small")?.textContent,
    ]),
  ).toEqual([
    ["My", "MySQL", "数据库元数据"],
    ["Pg", "PostgreSQL", "数据库元数据"],
    ["Or", "Oracle", "数据库元数据"],
    ["MS", "SQL Server", "数据库元数据"],
    ["Do", "Doris", "数据库元数据"],
  ]);
  expect(
    within(dialog).getByRole("button", { name: /^PostgreSQL/ }),
  ).toHaveAttribute("aria-pressed", "false");
});

it("MySQL 数据库留空的提示；采集范围逐层说明含义与写法（层级按 OpenMetadata 连接器核实）", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: [] } }]);
  open();
  const dialog = await stepOne("mes", "plant-mes", "MySQL");
  expect(
    within(dialog).getByLabelText("数据库（选填）"),
  ).toHaveAccessibleDescription(
    /留空会采集账号可见的全部库，包括 information_schema 等系统库；建议填写业务库名/,
  );
  // 第 3 步各层说明由 scopeHelp 生成（渲染见“过滤规则非法正则拦截”用例进入第 3 步时的断言）
  const { scopeHelp } = await import("../features/sources/format");
  expect(scopeHelp("Mysql")).toEqual({
    rule: expect.stringMatching(/从名称开头匹配.*不区分大小写.*\^名称\$/),
    databaseFilterPattern: expect.stringMatching(/固定为 default/),
    schemaFilterPattern: expect.stringMatching(/物理库/),
    tableFilterPattern: expect.stringMatching(/表或视图名/),
  });
  expect(scopeHelp("Postgres").databaseFilterPattern).toMatch(
    /连接时填写的数据库/,
  );
  expect(scopeHelp("Postgres").schemaFilterPattern).toMatch(/public/);
  expect(scopeHelp("Postgres").schemaFilterPattern).toMatch(
    /information_schema/,
  );
  expect(scopeHelp("Oracle").databaseFilterPattern).toMatch(/固定为 default/);
  expect(scopeHelp("Mssql").schemaFilterPattern).toMatch(/dbo/);
});
