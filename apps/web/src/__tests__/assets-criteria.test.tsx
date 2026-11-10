import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router";
import { expect, it } from "vitest";
import {
  AssetsCriteriaProvider,
  criteriaReducer,
  initialCriteria,
  useAssetsCriteria,
} from "../features/assets/criteria";

// 006 data-model 第 2 节：搜索条件的规则；只在本次会话（内存）中保留，不写入地址（D9）

it("改变关键词、范围、位置、筛选或排序时页码回到 1", () => {
  const paged = { ...initialCriteria, page: 4 };
  for (const action of [
    { type: "keyword", keyword: "工单" },
    { type: "scope", scope: "table" },
    { type: "browse", path: [{ level: "root", value: "databases" }] },
    {
      type: "filter",
      dimension: "tier",
      values: ["tier.tier1"],
      includeNone: false,
    },
    { type: "sort", field: "name", order: "asc" },
    { type: "entityType", entityType: "table" },
  ] as const) {
    expect(criteriaReducer(paged, action).page).toBe(1);
  }
  expect(criteriaReducer(paged, { type: "page", page: 2 }).page).toBe(2);
});

it("清除全部清空关键词、位置与筛选", () => {
  const s = criteriaReducer(
    criteriaReducer(
      criteriaReducer(initialCriteria, { type: "keyword", keyword: "x" }),
      { type: "browse", path: [{ level: "root", value: "databases" }] },
    ),
    { type: "filter", dimension: "owner", values: [], includeNone: true },
  );
  const cleared = criteriaReducer(s, { type: "clearAll" });
  expect(cleared.keyword).toBe("");
  expect(cleared.browsePath).toEqual([]);
  expect(cleared.filters).toEqual({});
});

it("删除某一层位置条件时连同下层一起删除", () => {
  const path = [
    { level: "root", value: "databases" },
    { level: "serviceType", value: "mysql" },
    { level: "service", value: "devtest-mes" },
    { level: "database", value: "default" },
  ] as const;
  const s = criteriaReducer(initialCriteria, {
    type: "browse",
    path: [...path],
  });
  const cut = criteriaReducer(s, { type: "removeBrowseLevel", index: 2 });
  expect(cut.browsePath.map((p) => p.level)).toEqual(["root", "serviceType"]);
});

it("位置条件第一项必须是 root、不能跳层、最多 6 层", () => {
  expect(() =>
    criteriaReducer(initialCriteria, {
      type: "browse",
      path: [{ level: "service", value: "x" }],
    }),
  ).toThrow();
  expect(() =>
    criteriaReducer(initialCriteria, {
      type: "browse",
      path: [
        { level: "root", value: "databases" },
        { level: "service", value: "x" },
      ],
    }),
  ).toThrow();
});

it("每页条数只能是 15 / 25 / 50，且不超过 10000 条结果窗口", () => {
  expect(() =>
    criteriaReducer(initialCriteria, { type: "pageSize", pageSize: 20 }),
  ).toThrow();
  const s = criteriaReducer(initialCriteria, {
    type: "pageSize",
    pageSize: 50,
  });
  expect(s.pageSize).toBe(50);
  expect(() => criteriaReducer(s, { type: "page", page: 201 })).toThrow();
  expect(criteriaReducer(s, { type: "page", page: 200 }).page).toBe(200);
});

function Probe() {
  const { criteria, dispatch } = useAssetsCriteria();
  const navigate = useNavigate();
  const loc = useLocation();
  return (
    <div>
      <output aria-label="关键词">{criteria.keyword}</output>
      <output aria-label="地址参数">{loc.search}</output>
      <button onClick={() => dispatch({ type: "keyword", keyword: "工单" })}>
        设关键词
      </button>
      <button onClick={() => navigate("/assets/sources")}>去子视图</button>
      <button onClick={() => navigate("/assets")}>回探索</button>
    </div>
  );
}

it("同一页面内切换子路由后条件保留，且不写入地址", async () => {
  render(
    <MemoryRouter initialEntries={["/assets"]}>
      <AssetsCriteriaProvider>
        <Routes>
          <Route path="/assets/*" element={<Probe />} />
        </Routes>
      </AssetsCriteriaProvider>
    </MemoryRouter>,
  );
  await userEvent.click(screen.getByRole("button", { name: "设关键词" }));
  await userEvent.click(screen.getByRole("button", { name: "去子视图" }));
  await act(async () => {
    await userEvent.click(screen.getByRole("button", { name: "回探索" }));
  });
  expect(screen.getByLabelText("关键词")).toHaveTextContent("工单");
  expect(screen.getByLabelText("地址参数")).toBeEmptyDOMElement();
});
