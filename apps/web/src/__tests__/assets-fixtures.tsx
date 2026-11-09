// 006 组件测试夹具：模拟 BFF 响应（仅测试使用，不进入生产代码；断言基于这些夹具，不基于原型示例值）
import { render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { App } from "../App";
import { stubBff } from "./sources-fixtures";

export const ME = {
  tenant_id: "local",
  user_id: "u-1",
  display_name: "测试工程师",
  roles: ["ai-engineer"],
};

export const TABLE_FQN = "devtest-mes.default.mes.work_order";

export function hit(over: Record<string, unknown> = {}) {
  return {
    ref: { entityType: "table", id: "id-wo", fqn: TABLE_FQN },
    name: "work_order",
    displayName: "生产工单",
    serviceType: "Mysql",
    breadcrumb: [
      { entityType: "databaseService", label: "devtest-mes" },
      { entityType: "database", label: "default" },
      { entityType: "databaseSchema", label: "mes" },
    ],
    nameHighlight: [
      { text: "生产", match: false },
      { text: "工单", match: true },
    ],
    descriptionHighlight: [{ text: "生产工单主表", match: false }],
    description: "生产工单主表",
    governance: {
      owners: [
        {
          id: "00000000-0000-0000-0000-00000000000a",
          type: "team",
          name: "admin",
        },
      ],
      domains: [
        {
          id: "00000000-0000-0000-0000-0000000000d1",
          type: "domain",
          name: "DevTestProduction",
          displayName: "开发态-生产域",
        },
      ],
      dataProducts: [],
      tier: "Tier.Tier1",
      dataLevel: "数据级别.二级",
      certification: "Certification.Gold",
      glossaryTerms: [],
      tags: [],
      origin: "devTest",
    },
    origin: "devTest",
    matchedFields: [
      { field: "displayName", count: 1 },
      { field: "description", count: 2 },
    ],
    parentTable: null,
    columnName: null,
    ...over,
  };
}

export const metricHit = hit({
  ref: { entityType: "metric", id: "id-m", fqn: "line_yield" },
  name: "line_yield",
  displayName: "产线良率",
  breadcrumb: [],
  nameHighlight: [],
  descriptionHighlight: [],
  description: "产线良率",
  governance: {
    ...hit().governance,
    certification: null,
    tier: null,
    dataLevel: null,
    origin: "collected",
  },
  origin: "collected",
  matchedFields: [],
});

export function page(hits: unknown[], total = hits.length) {
  return {
    total,
    page: 1,
    pageSize: 15,
    windowLimited: total > 10000,
    index: "table",
    hits,
  };
}

export const summary = {
  ref: { entityType: "table", id: "id-wo", fqn: TABLE_FQN },
  name: "work_order",
  displayName: "生产工单",
  description: "生产工单主表",
  breadcrumb: hit().breadcrumb,
  governance: {
    ...hit().governance,
    glossaryTerms: ["ContextureDevGlossary.工单"],
    tags: ["ContextureDevSample.生产相关"],
  },
  columns: [
    {
      name: "wo_no",
      dataTypeDisplay: "varchar(32)",
      constraint: "PRIMARY_KEY",
      description: "工单号",
      displayName: null,
      tags: ["数据级别.一级"],
      dataLevel: "数据级别.一级",
    },
  ],
};

type R = {
  method?: string;
  path: string | RegExp;
  status?: number;
  body: unknown;
};

export function stubAssets(routes: R[]) {
  return stubBff([
    { path: "/bff/v1/me", body: ME },
    { path: "/bff/v1/sources", body: { data: [] } },
    ...routes,
  ]);
}

function Where() {
  const loc = useLocation();
  return (
    <>
      <output aria-label="当前地址">{decodeURIComponent(loc.pathname)}</output>
      <output aria-label="跳转状态">{JSON.stringify(loc.state ?? null)}</output>
    </>
  );
}

export function openAssets(path = "/assets") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <Where />
    </MemoryRouter>,
  );
}
