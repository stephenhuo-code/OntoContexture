import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { renderQ } from "./query-wrapper";
import { afterEach, expect, it, vi } from "vitest";
import { AssetsWorkspace } from "../features/assets/AssetsWorkspace";
import { sourcesFixture, stubBff } from "./sources-fixtures";

// US3 组件测试：断言基于夹具（BFF 目录实体），不基于原型示例值
afterEach(() => vi.unstubAllGlobals());

const enc = encodeURIComponent;
const service = {
  entityType: "databaseService",
  id: "aaaaaaaa-0000-4000-8000-000000000001",
  name: "fixture-mes",
  fullyQualifiedName: "fixture-mes",
  governance: {
    displayName: "夹具 MES",
    tags: [],
    glossaryTerms: [],
    owners: [],
    domains: [],
    dataProducts: [],
  },
  children: [
    {
      entityType: "database",
      name: "default",
      fullyQualifiedName: "fixture-mes.default",
      displayName: null,
      description: null,
      childCount: 1,
    },
  ],
};
const database = {
  entityType: "database",
  id: "aaaaaaaa-0000-4000-8000-000000000002",
  name: "default",
  fullyQualifiedName: "fixture-mes.default",
  governance: {
    displayName: null,
    description: null,
    tags: [],
    glossaryTerms: [],
    owners: [],
    domains: [],
    dataProducts: [],
  },
  children: [
    {
      entityType: "databaseSchema",
      name: "mes",
      fullyQualifiedName: "fixture-mes.default.mes",
      displayName: null,
      description: "生产库",
      childCount: 2,
    },
  ],
};
const schema = {
  entityType: "databaseSchema",
  id: "aaaaaaaa-0000-4000-8000-000000000003",
  name: "mes",
  fullyQualifiedName: "fixture-mes.default.mes",
  governance: {
    displayName: null,
    description: "生产库",
    tags: [],
    glossaryTerms: [],
    owners: [],
    domains: [],
    dataProducts: [],
  },
  children: [
    {
      entityType: "table",
      name: "work_order",
      fullyQualifiedName: "fixture-mes.default.mes.work_order",
      displayName: "工单",
      description: null,
      childCount: 2,
    },
    {
      entityType: "table",
      name: "line",
      fullyQualifiedName: "fixture-mes.default.mes.line",
      displayName: null,
      description: null,
      childCount: 1,
    },
  ],
};
const table = (name: string, constraints: unknown[], columns: unknown[]) => ({
  entityType: "table",
  id: "aaaaaaaa-0000-4000-8000-000000000004",
  name,
  fullyQualifiedName: `fixture-mes.default.mes.${name}`,
  governance: {
    displayName: name === "work_order" ? "工单" : null,
    tags: [],
    glossaryTerms: [],
    owners: [],
    domains: [],
    dataProducts: [],
  },
  table: { tableType: "Regular", constraints, schemaDefinition: null, columns },
});
const workOrder = table(
  "work_order",
  [{ constraintType: "PRIMARY_KEY", columns: ["wo_no"] }],
  [
    {
      name: "wo_no",
      dataTypeDisplay: "varchar(20)",
      constraint: "PRIMARY_KEY",
      displayName: null,
      description: "工单号",
      tags: ["PII.Sensitive"],
      glossaryTerms: [],
    },
    {
      name: "qty",
      dataTypeDisplay: "int",
      constraint: null,
      displayName: null,
      description: null,
      tags: [],
      glossaryTerms: ["Glossary.Quantity"],
    },
  ],
);
const line = table(
  "line",
  [],
  [
    {
      name: "code",
      dataTypeDisplay: "varchar(8)",
      constraint: null,
      displayName: null,
      description: null,
      tags: [],
      glossaryTerms: [],
    },
  ],
);

const routes = [
  { path: "/bff/v1/sources", body: { data: sourcesFixture } },
  { path: "/bff/v1/catalog/databaseService/fixture-mes", body: service },
  { path: "/bff/v1/catalog/database/fixture-mes.default", body: database },
  {
    path: "/bff/v1/catalog/databaseSchema/fixture-mes.default.mes",
    body: schema,
  },
  {
    path: "/bff/v1/catalog/table/fixture-mes.default.mes.work_order",
    body: workOrder,
  },
  { path: "/bff/v1/catalog/table/fixture-mes.default.mes.line", body: line },
  {
    path: "/bff/v1/sources/fixture-mes",
    body: {
      ...sourcesFixture[0],
      connection: {
        hostPort: "h:3306",
        username: "u",
        database: "mes",
        tls: false,
      },
      scope: { includeViews: true },
    },
  },
];

function Where() {
  const loc = useLocation();
  return (
    <output aria-label="当前地址">{decodeURIComponent(loc.pathname)}</output>
  );
}

// 006：005 的目录树由数据资产页的浏览树取代（FR-006），树的用例见 assets-browse.test.tsx
function open(path: string) {
  return renderQ(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/assets/*" element={<AssetsWorkspace />} />
      </Routes>
      <Where />
    </MemoryRouter>,
  );
}

it("数据库资产页：眉标、标题、FQN、面包屑只到当前层级、返回所属数据源，无源级控制", async () => {
  stubBff(routes);
  open(`/assets/database/${enc("fixture-mes.default")}`);
  expect(await screen.findByText("METADATA CATALOG")).toBeVisible();
  expect(
    screen.getByRole("heading", { level: 2, name: "default" }),
  ).toBeVisible();
  expect(screen.getAllByText("fixture-mes.default").length).toBeGreaterThan(0);
  const crumbs = screen.getByRole("navigation", { name: "资产层级" });
  expect(crumbs).toHaveTextContent(/^fixture-mes›default$/);
  expect(within(crumbs).getByText("default")).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.getByRole("link", { name: "← 返回所属数据源" }),
  ).toHaveAttribute("href", "/assets/sources/fixture-mes");
  expect(
    screen.queryByRole("button", { name: /配置连接与范围|继续配置/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("tab", { name: "采集任务" }),
  ).not.toBeInTheDocument();
  const list = screen.getByRole("table", { name: "Schema 列表" });
  expect(within(list).getByRole("row", { name: /mes/ })).toHaveTextContent(
    "生产库",
  );
  expect(within(list).getByRole("row", { name: /mes/ })).toHaveTextContent("2");
});

it("表资产页：结构信息只显示 OM 实际约束、字段 PK 徽章、标签与术语；切换同 Schema 下的表", async () => {
  stubBff(routes);
  open(`/assets/table/${enc("fixture-mes.default.mes.work_order")}`);
  expect(
    await screen.findByRole("heading", { level: 2, name: "工单" }),
  ).toBeVisible();
  expect(
    screen.getByRole("navigation", { name: "资产层级" }),
  ).toHaveTextContent(/^fixture-mes›default›mes›work_order$/);
  const info = screen.getByRole("region", { name: "结构信息" });
  expect(info).toHaveTextContent("Regular");
  expect(info).toHaveTextContent("2");
  expect(info).toHaveTextContent("PRIMARY_KEY (wo_no)");
  const cols = screen.getByRole("table", { name: "字段元数据" });
  const wo = within(cols).getByRole("row", { name: /wo_no/ });
  expect(within(wo).getByText("PK")).toBeVisible();
  expect(wo).toHaveTextContent("varchar(20)");
  expect(wo).toHaveTextContent("工单号");
  expect(wo).toHaveTextContent("PII.Sensitive");
  const qty = within(cols).getByRole("row", { name: /qty/ });
  expect(within(qty).queryByText("PK")).not.toBeInTheDocument();
  expect(qty).toHaveTextContent("Glossary.Quantity");

  const select = await screen.findByRole("combobox", { name: "选择数据表" });
  expect(
    within(select)
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["工单 · work_order", "line"]);
  await userEvent.selectOptions(select, "fixture-mes.default.mes.line");
  expect(
    await screen.findByRole("heading", { level: 2, name: "line" }),
  ).toBeVisible();
  expect(screen.getByRole("region", { name: "结构信息" })).toHaveTextContent(
    "源未提供约束信息",
  );
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(
    "/assets/table/fixture-mes.default.mes.line",
  );
});

it("已采集元数据页签：列出数据库与 Schema 数；未采集的数据源显示暂无元数据", async () => {
  stubBff(routes);
  const view = open("/assets/sources/fixture-mes?tab=metadata");
  const list = await screen.findByRole("table", { name: "数据库目录" });
  expect(within(list).getByRole("link", { name: "default" })).toHaveAttribute(
    "href",
    `/assets/database/${enc("fixture-mes.default")}`,
  );
  expect(within(list).getByRole("row", { name: /default/ })).toHaveTextContent(
    "1",
  );
  view.unmount();

  stubBff([
    {
      path: "/bff/v1/sources/fixture-erp",
      body: {
        ...sourcesFixture[2],
        connection: {
          hostPort: "h:1521",
          username: "u",
          database: "ERP",
          tls: false,
        },
        scope: { includeViews: true },
      },
    },
    {
      path: "/bff/v1/catalog/databaseService/fixture-erp",
      body: {
        ...service,
        name: "fixture-erp",
        fullyQualifiedName: "fixture-erp",
        children: [],
      },
    },
  ]);
  open("/assets/sources/fixture-erp?tab=metadata");
  expect(await screen.findByText("暂无元数据")).toBeVisible();
});

it("目录读取失败时如实显示错误码，不显示示例数据", async () => {
  stubBff([
    {
      path: "/bff/v1/catalog/table/fixture-mes.default.mes.work_order",
      status: 502,
      body: {
        code: "upstream.unavailable",
        message: "OpenMetadata 不可用",
        trace_id: "t-1",
      },
    },
  ]);
  open(`/assets/table/${enc("fixture-mes.default.mes.work_order")}`);
  expect(await screen.findByText("OpenMetadata 不可用")).toBeVisible();
  expect(screen.getByText(/upstream.unavailable/)).toBeVisible();
  expect(
    screen.queryByRole("table", { name: "字段元数据" }),
  ).not.toBeInTheDocument();
});

it("单列主键只在 OM 列级约束中时，表约束据列约束显示", async () => {
  const station = table(
    "station",
    [],
    [
      {
        name: "code",
        dataTypeDisplay: "varchar(8)",
        constraint: "PRIMARY_KEY",
        displayName: null,
        description: null,
        tags: [],
        glossaryTerms: [],
      },
      {
        name: "sn",
        dataTypeDisplay: "varchar(8)",
        constraint: "UNIQUE",
        displayName: null,
        description: null,
        tags: [],
        glossaryTerms: [],
      },
    ],
  );
  stubBff([
    ...routes,
    {
      path: "/bff/v1/catalog/table/fixture-mes.default.mes.station",
      body: station,
    },
  ]);
  open(`/assets/table/${enc("fixture-mes.default.mes.station")}`);
  const info = await screen.findByRole("region", { name: "结构信息" });
  expect(info).toHaveTextContent("PRIMARY_KEY (code)；UNIQUE (sn)");
});
