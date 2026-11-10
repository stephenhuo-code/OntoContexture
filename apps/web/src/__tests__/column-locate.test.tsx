import { screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AssetsWorkspace } from "../features/assets/AssetsWorkspace";
import { renderQ } from "./query-wrapper";
import { stubBff } from "./sources-fixtures";

const TABLE = "fixture-mes.default.mes.work_order";
const entity = {
  entityType: "table",
  id: "00000000-0000-4000-8000-000000000001",
  name: "work_order",
  fullyQualifiedName: TABLE,
  governance: {},
  children: [],
  table: {
    tableType: "Regular",
    constraints: [],
    columns: [
      {
        name: "wo_no",
        dataTypeDisplay: "varchar(32)",
        constraint: "PRIMARY_KEY",
        tags: [],
        glossaryTerms: [],
      },
      {
        name: "line_code",
        dataTypeDisplay: "varchar(32)",
        constraint: null,
        tags: [],
        glossaryTerms: [],
      },
    ],
  },
};
const scroll = vi.fn();
beforeEach(() => {
  scroll.mockClear();
  Element.prototype.scrollIntoView = scroll;
});
afterEach(() => vi.unstubAllGlobals());

function open(state?: unknown) {
  stubBff([
    { path: `/bff/v1/catalog/table/${TABLE}`, body: entity },
    {
      path: /\/bff\/v1\/catalog\/database/,
      body: { ...entity, entityType: "database", table: undefined },
    },
    { path: "/bff/v1/sources", body: { data: [] } },
    { method: "POST", path: "/bff/v1/assets/browse", body: { nodes: [] } },
  ]);
  renderQ(
    <MemoryRouter
      initialEntries={[
        { pathname: `/assets/table/${encodeURIComponent(TABLE)}`, state },
      ]}
    >
      <Routes>
        <Route path="/assets/*" element={<AssetsWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("由列结果进入时滚动到该列并高亮，地址中不出现列名（Q3）", async () => {
  open({ column: "line_code" });
  const table = await screen.findByRole("table", { name: "字段元数据" });
  const row = within(table).getByRole("row", { name: /line_code/ });
  expect(row).toHaveAttribute("aria-current", "true");
  expect(scroll).toHaveBeenCalled();
  expect(within(table).getByRole("row", { name: /wo_no/ })).not.toHaveAttribute(
    "aria-current",
  );
});

it("没有定位状态时不高亮任何列", async () => {
  open();
  const table = await screen.findByRole("table", { name: "字段元数据" });
  expect(table.querySelector('[aria-current="true"]')).toBeNull();
  expect(scroll).not.toHaveBeenCalled();
});
