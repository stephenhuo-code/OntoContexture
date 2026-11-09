import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { openAssets, stubAssets } from "./assets-fixtures";

afterEach(() => vi.unstubAllGlobals());

const term = {
  ref: {
    entityType: "glossaryTerm",
    id: "g1",
    fqn: "ContextureDevGlossary.工单",
  },
  name: "工单",
  displayName: "工单",
  description: "开发态样例术语：生产工单。",
  glossary: {
    id: "00000000-0000-0000-0000-0000000000g0",
    type: "glossary",
    name: "ContextureDevGlossary",
  },
  parent: null,
  synonyms: ["Work Order"],
  relatedTerms: [],
  references: [{ name: "手册", endpoint: "https://example.invalid/wo" }],
  owners: [
    { id: "00000000-0000-0000-0000-00000000000a", type: "team", name: "admin" },
  ],
  reviewers: [],
  domains: [],
  tags: ["ContextureDevTest.DevTestMetadata"],
  entityStatus: "Approved",
  origin: "devTest",
};
const tag = {
  ref: { entityType: "tag", id: "t1", fqn: "数据级别.一级" },
  name: "一级",
  displayName: null,
  description: "公开或内部一般数据",
  classification: {
    id: "00000000-0000-0000-0000-0000000000c1",
    type: "classification",
    name: "数据级别",
  },
  parent: null,
  owners: [],
  reviewers: [],
  domains: [],
  deprecated: false,
};

function setup(status = 200) {
  stubAssets([
    { method: "POST", path: "/bff/v1/assets/browse", body: { nodes: [] } },
    {
      method: "POST",
      path: "/bff/v1/assets/type-counts",
      body: { counts: [], topHitType: null, defaultType: null },
    },
    {
      method: "POST",
      path: "/bff/v1/assets/search",
      body: { total: 0, page: 1, pageSize: 15, windowLimited: false, hits: [] },
    },
    {
      path: "/bff/v1/governance/glossary-terms/ContextureDevGlossary.工单",
      status,
      body:
        status === 200
          ? term
          : {
              code: "catalog.not_found",
              message: "OpenMetadata 中不存在 ContextureDevGlossary.工单",
              trace_id: "",
            },
    },
    { path: "/bff/v1/governance/tags/数据级别.一级", body: tag },
  ]);
}

const labels = () => screen.getAllByRole("term").map((t) => t.textContent);

it("业务术语只读详情：14 项字段，没有编辑入口，可返回探索视图（FR-013）", async () => {
  setup();
  openAssets(
    `/assets/glossaryTerm/${encodeURIComponent("ContextureDevGlossary.工单")}`,
  );
  const page = await screen.findByRole("region", { name: "业务术语详情" });
  expect(labels()).toEqual([
    "名称",
    "显示名称",
    "完整名称（FQN）",
    "所属术语表",
    "上级术语",
    "描述",
    "同义词",
    "相关术语",
    "参考链接",
    "负责人",
    "评审人",
    "业务域",
    "分类标签",
    "状态",
  ]);
  expect(page).toHaveTextContent("Work Order");
  expect(page).toHaveTextContent("评审人未设置");
  expect(page).toHaveTextContent("上级术语—");
  expect(
    within(page).queryByRole("button", { name: /编辑/ }),
  ).not.toBeInTheDocument();
  await userEvent.click(
    within(page).getByRole("link", { name: "返回探索视图" }),
  );
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(/^\/assets$/);
});

it("分类标签只读详情：10 项字段", async () => {
  setup();
  openAssets(`/assets/tag/${encodeURIComponent("数据级别.一级")}`);
  await screen.findByRole("region", { name: "分类标签详情" });
  expect(labels()).toEqual([
    "名称",
    "显示名称",
    "完整名称（FQN）",
    "所属分类",
    "上级标签",
    "描述",
    "负责人",
    "评审人",
    "业务域",
    "是否已弃用",
  ]);
  expect(
    screen.getByRole("region", { name: "分类标签详情" }),
  ).toHaveTextContent("负责人未分配");
});

it("术语不存在时显示真实的「未找到」错误", async () => {
  setup(404);
  openAssets(
    `/assets/glossaryTerm/${encodeURIComponent("ContextureDevGlossary.工单")}`,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("未找到");
  expect(screen.getByRole("alert")).toHaveTextContent("catalog.not_found");
});
