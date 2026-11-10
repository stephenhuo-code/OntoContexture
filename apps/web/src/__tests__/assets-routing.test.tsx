import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { LegacySourcesRedirect } from "../features/assets/LegacySourcesRedirect";
import { assetHref, sourceHref } from "../features/sources/format";

afterEach(() => vi.unstubAllGlobals());

function Where() {
  const loc = useLocation();
  return (
    <output aria-label="当前地址">{`${decodeURIComponent(loc.pathname)}${loc.search}`}</output>
  );
}

function open(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/sources/*" element={<LegacySourcesRedirect />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  );
}

// 006 D1 / FR-002：旧 /sources/* 地址转到 /assets 下对应的新地址
it.each([
  ["/sources", "/assets/sources"],
  ["/sources/", "/assets/sources"],
  ["/sources/mock-mes", "/assets/sources/mock-mes"],
  ["/sources/mock-mes?tab=tasks", "/assets/sources/mock-mes?tab=tasks"],
  [
    "/sources/mock-mes/assets/table/mock-mes.default.mes.work_order",
    "/assets/table/mock-mes.default.mes.work_order",
  ],
  [
    "/sources/mock-mes/assets/database/mock-mes.default",
    "/assets/database/mock-mes.default",
  ],
  [
    "/sources/mock-mes/assets/databaseService/mock-mes",
    "/assets/sources/mock-mes",
  ],
])("旧地址 %s 转到 %s", async (from, to) => {
  open(from);
  expect(await screen.findByLabelText("当前地址")).toHaveTextContent(to);
});

it("新地址：数据源详情在 /assets/sources 下，资产详情在 /assets/{类型}/{fqn} 下", () => {
  expect(sourceHref("mock-mes")).toBe("/assets/sources/mock-mes");
  expect(assetHref("mock-mes", "databaseService", "mock-mes")).toBe(
    "/assets/sources/mock-mes",
  );
  expect(assetHref("mock-mes", "table", "mock-mes.default.mes.a b")).toBe(
    `/assets/table/${encodeURIComponent("mock-mes.default.mes.a b")}`,
  );
});
