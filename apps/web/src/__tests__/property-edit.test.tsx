import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { renderQ } from "./query-wrapper";
import { afterEach, expect, it, vi } from "vitest";
import { AssetsWorkspace } from "../features/assets/AssetsWorkspace";
import { sourcesFixture, stubBff } from "./sources-fixtures";

// US4 组件测试：选项与实体均来自夹具（BFF 响应），不基于原型示例值
afterEach(() => vi.unstubAllGlobals());

const enc = encodeURIComponent;
const TABLE = "fixture-mes.default.mes.work_order";
const D1 = {
  id: "d1000000-0000-4000-8000-000000000001",
  type: "domain",
  name: "Production",
};
const D2 = {
  id: "d2000000-0000-4000-8000-000000000002",
  type: "domain",
  name: "Quality",
};
const U1 = {
  id: "a1000000-0000-4000-8000-000000000001",
  type: "user",
  name: "engineer1",
  displayName: "工程师一",
};
const options = {
  users: [
    U1,
    {
      id: "a2000000-0000-4000-8000-000000000002",
      type: "user",
      name: "admin1",
    },
  ],
  teams: [
    {
      id: "b1000000-0000-4000-8000-000000000001",
      type: "team",
      name: "ai-engineer",
    },
  ],
  domains: [D1, D2],
  dataProducts: [
    {
      id: "c1000000-0000-4000-8000-000000000001",
      type: "dataProduct",
      name: "MES 工单",
      domains: [D1],
    },
    {
      id: "c2000000-0000-4000-8000-000000000002",
      type: "dataProduct",
      name: "质量追溯",
      domains: [D2],
    },
  ],
  classifications: [
    {
      name: "PII",
      mutuallyExclusive: true,
      tags: ["PII.Sensitive", "PII.NonSensitive"],
    },
    {
      name: "Source",
      mutuallyExclusive: false,
      tags: ["Source.MES", "Source.ERP"],
    },
  ],
  glossaryTerms: ["Glossary.Quantity"],
};
const governance = (over: Record<string, unknown> = {}) => ({
  displayName: null,
  description: null,
  owners: [],
  domains: [],
  tier: null,
  tags: [],
  glossaryTerms: [],
  dataProducts: [],
  retentionPeriod: null,
  inheritedFrom: {},
  ...over,
});
const table = (gov: Record<string, unknown>) => ({
  entityType: "table",
  id: "aaaaaaaa-0000-4000-8000-000000000004",
  name: "work_order",
  fullyQualifiedName: TABLE,
  governance: governance(gov),
  table: {
    tableType: "Regular",
    constraints: [],
    schemaDefinition: null,
    columns: [
      {
        name: "qty",
        dataTypeDisplay: "int",
        constraint: null,
        displayName: null,
        description: null,
        tags: [],
        glossaryTerms: [],
      },
    ],
  },
});
const schema = {
  entityType: "databaseSchema",
  id: "aaaaaaaa-0000-4000-8000-000000000003",
  name: "mes",
  fullyQualifiedName: "fixture-mes.default.mes",
  governance: governance({
    domains: [D1],
    inheritedFrom: {
      domains: {
        entityType: "databaseService",
        fullyQualifiedName: "fixture-mes",
      },
    },
  }),
  children: [
    {
      entityType: "table",
      name: "work_order",
      fullyQualifiedName: TABLE,
      displayName: null,
      description: null,
      childCount: 1,
    },
  ],
};
const inheritedTable = table({
  domains: [D1],
  owners: [U1],
  retentionPeriod: "P30D",
  inheritedFrom: {
    domains: {
      entityType: "databaseService",
      fullyQualifiedName: "fixture-mes",
    },
    owners: {
      entityType: "database",
      fullyQualifiedName: "fixture-mes.default",
    },
    retentionPeriod: {
      entityType: "databaseSchema",
      fullyQualifiedName: "fixture-mes.default.mes",
    },
  },
});

function open(entity: unknown, patched?: unknown, status = 200) {
  const calls = stubBff([
    { path: `/bff/v1/catalog/table/${TABLE}`, body: entity },
    {
      path: "/bff/v1/catalog/databaseSchema/fixture-mes.default.mes",
      body: schema,
    },
    { path: "/bff/v1/governance/options", body: options },
    { path: "/bff/v1/sources", body: { data: sourcesFixture } },
    {
      method: "PATCH",
      path: `/bff/v1/catalog/table/${TABLE}`,
      status,
      body: patched ?? entity,
    },
  ]);
  renderQ(
    <MemoryRouter initialEntries={[`/assets/table/${enc(TABLE)}`]}>
      <Routes>
        <Route path="/assets/*" element={<AssetsWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );
  return calls;
}

const patches = (calls: { method: string; body?: unknown }[]) =>
  calls.filter((c) => c.method === "PATCH").map((c) => c.body);

async function editTable() {
  const card = await screen.findByRole("region", { name: "数据表属性" });
  await userEvent.click(within(card).getByRole("button", { name: "编辑属性" }));
  return screen.findByRole("dialog", { name: "编辑数据表属性" });
}

it("属性卡片标注继承来源与单独设置", async () => {
  open(table({ ...inheritedTable.governance, displayName: "工单" }));
  const card = await screen.findByRole("region", { name: "数据表属性" });
  expect(
    within(card).getByText("继承自 数据库 · fixture-mes.default"),
  ).toBeVisible();
  expect(within(card).getByText("继承自 数据源 · fixture-mes")).toBeVisible();
  expect(
    within(card).getByText("继承自 Schema · fixture-mes.default.mes"),
  ).toBeVisible();
  expect(within(card).getByText("工程师一")).toBeVisible();
});

it("选项来自 BFF；保存只提交修改的字段并回显；取消不保存", async () => {
  const calls = open(
    inheritedTable,
    table({ ...inheritedTable.governance, displayName: "生产工单" }),
  );
  let dialog = await editTable();
  expect(
    within(dialog).getByRole("combobox", { name: "业务域" }),
  ).toHaveTextContent("继承上级（Production）");
  expect(
    within(within(dialog).getByRole("combobox", { name: "业务域" }))
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["继承上级（Production）", "Production", "Quality"]);
  await userEvent.type(within(dialog).getByLabelText("显示名称"), "临时");
  await userEvent.click(within(dialog).getByRole("button", { name: "取消" }));
  expect(patches(calls)).toEqual([]);

  dialog = await editTable();
  expect(within(dialog).getByLabelText("显示名称")).toHaveValue("");
  await userEvent.type(within(dialog).getByLabelText("显示名称"), "生产工单");
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(patches(calls)).toEqual([{ displayName: "生产工单" }]);
  expect(
    await screen.findByRole("heading", { level: 2, name: "生产工单" }),
  ).toBeVisible();
});

it("选择“继承上级”清空单独设置的域；负责人不选择时清空恢复继承", async () => {
  const own = table({ domains: [D2], owners: [U1], inheritedFrom: {} });
  const calls = open(own);
  const dialog = await editTable();
  await userEvent.selectOptions(
    within(dialog).getByRole("combobox", { name: "业务域" }),
    "",
  );
  await userEvent.click(
    within(dialog).getByRole("checkbox", { name: "工程师一" }),
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(patches(calls)).toEqual([{ domain: null, owners: null }]);
});

it("数据产品与有效业务域不匹配时提示并阻止保存", async () => {
  const calls = open(inheritedTable);
  const dialog = await editTable();
  await userEvent.click(
    within(dialog).getByRole("checkbox", { name: /质量追溯/ }),
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(within(dialog).getByRole("alert")).toHaveTextContent(
    "数据产品与业务域不匹配",
  );
  expect(patches(calls)).toEqual([]);
  await userEvent.selectOptions(
    within(dialog).getByRole("combobox", { name: "业务域" }),
    D2.id,
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(patches(calls)).toEqual([
    {
      domain: { id: D2.id, type: "domain" },
      dataProducts: [{ id: options.dataProducts[1]!.id, type: "dataProduct" }],
    },
  ]);
});

it("互斥分类下勾选新标签替换同分类已选项；非互斥分类可多选", async () => {
  const calls = open(table({ tags: ["PII.Sensitive"] }));
  const dialog = await editTable();
  await userEvent.click(
    within(dialog).getByRole("checkbox", { name: "PII.NonSensitive" }),
  );
  expect(
    within(dialog).getByRole("checkbox", { name: "PII.Sensitive" }),
  ).not.toBeChecked();
  await userEvent.click(
    within(dialog).getByRole("checkbox", { name: "Source.MES" }),
  );
  await userEvent.click(
    within(dialog).getByRole("checkbox", { name: "Source.ERP" }),
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(patches(calls)).toEqual([
    { tags: ["PII.NonSensitive", "Source.MES", "Source.ERP"] },
  ]);
});

it("保留周期须为 ISO 8601 时长；留空恢复继承", async () => {
  const calls = open(table({ retentionPeriod: "P7D" }));
  const dialog = await editTable();
  const input = within(dialog).getByLabelText("保留周期");
  await userEvent.clear(input);
  await userEvent.type(input, "30 days");
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(within(dialog).getByRole("alert")).toHaveTextContent("ISO 8601");
  await userEvent.clear(input);
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(patches(calls)).toEqual([{ retentionPeriod: null }]);
});

it("BFF 校验失败如实显示错误码，弹窗保持打开", async () => {
  const calls = open(
    inheritedTable,
    {
      code: "governance.domain_mismatch",
      message: "数据产品与业务域不匹配",
      trace_id: "t-9",
    },
    400,
  );
  const dialog = await editTable();
  await userEvent.type(within(dialog).getByLabelText("描述"), "x");
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(await within(dialog).findByRole("alert")).toHaveTextContent(
    "governance.domain_mismatch",
  );
  expect(patches(calls)).toHaveLength(1);
});

it("HTML 输入按文本显示", async () => {
  open(
    table({
      displayName: "<img src=x onerror=alert(1)>",
      description: "<b>粗体</b>",
    }),
  );
  expect(
    await screen.findByRole("heading", {
      level: 2,
      name: "<img src=x onerror=alert(1)>",
    }),
  ).toBeVisible();
  expect(screen.getByText("<b>粗体</b>")).toBeVisible();
  expect(document.querySelector("img")).toBeNull();
});

it("字段行编辑只含显示名称、描述、标签与术语，按 columnName 提交", async () => {
  const calls = open(table({}));
  const cols = await screen.findByRole("table", { name: "字段元数据" });
  await userEvent.click(
    within(within(cols).getByRole("row", { name: /qty/ })).getByRole("button", {
      name: "编辑属性",
    }),
  );
  const dialog = await screen.findByRole("dialog", { name: "编辑字段属性" });
  expect(
    within(dialog).queryByRole("combobox", { name: "业务域" }),
  ).not.toBeInTheDocument();
  expect(within(dialog).queryByLabelText("保留周期")).not.toBeInTheDocument();
  expect(within(dialog).getByText(/qty · int/)).toBeVisible();
  await userEvent.type(within(dialog).getByLabelText("描述"), "数量");
  await userEvent.click(
    within(dialog).getByRole("checkbox", { name: "Glossary.Quantity" }),
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "保存属性" }),
  );
  expect(patches(calls)).toEqual([
    {
      columnName: "qty",
      description: "数量",
      glossaryTerms: ["Glossary.Quantity"],
    },
  ]);
});

// 006 Q4：005 子视图的属性卡片与编辑弹窗统一为「分级（Tier）」
it("属性卡片与编辑弹窗使用「分级（Tier）」文案", async () => {
  open(inheritedTable);
  const card = await screen.findByRole("region", { name: "数据表属性" });
  expect(within(card).getByText("分级")).toBeVisible();
  expect(within(card).queryByText("重要程度")).not.toBeInTheDocument();
  const dialog = await editTable();
  expect(within(dialog).getByLabelText("分级（Tier）")).toBeVisible();
  expect(within(dialog).queryByText(/重要程度/)).not.toBeInTheDocument();
});
