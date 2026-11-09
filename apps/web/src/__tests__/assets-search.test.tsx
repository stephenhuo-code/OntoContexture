import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  TABLE_FQN,
  hit,
  openAssets,
  page,
  stubAssets,
} from "./assets-fixtures";

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const suggestions = {
  groups: [
    {
      entityType: "table",
      items: [
        {
          ref: { entityType: "table", id: "id-wo", fqn: TABLE_FQN },
          label: "生产工单",
          location: TABLE_FQN,
          parentTable: null,
          columnName: null,
        },
      ],
    },
    {
      entityType: "tableColumn",
      items: [
        {
          ref: {
            entityType: "tableColumn",
            id: "id-c",
            fqn: `${TABLE_FQN}.wo_no`,
          },
          label: "wo_no",
          location: `${TABLE_FQN}.wo_no`,
          parentTable: { entityType: "table", id: "id-wo", fqn: TABLE_FQN },
          columnName: "wo_no",
        },
      ],
    },
    {
      entityType: "metric",
      items: [
        {
          ref: { entityType: "metric", id: "id-m", fqn: "line_yield" },
          label: "产线良率",
          location: "line_yield",
          parentTable: null,
          columnName: null,
        },
      ],
    },
  ],
};

function routes() {
  return [
    {
      method: "POST",
      path: "/bff/v1/assets/type-counts",
      body: {
        counts: [
          { entityType: "table", count: 2 },
          { entityType: "glossaryTerm", count: 1 },
        ],
        topHitType: "table",
        defaultType: "table",
      },
    },
    { method: "POST", path: "/bff/v1/assets/search", body: page([hit()]) },
    { path: "/bff/v1/assets/suggestions", body: suggestions },
    {
      path: /\/bff\/v1\/assets\/summary\//,
      body: {
        ref: hit().ref,
        name: "work_order",
        governance: hit().governance,
        columns: [],
      },
    },
  ];
}

const user = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

it("输入停顿 400ms 后才请求建议，并按类型分组显示名称与位置（FR-005）", async () => {
  const calls = stubAssets(routes());
  openAssets();
  const box = await screen.findByRole("searchbox", { name: "搜索数据资产" });
  await user().type(box, "工单");
  const sugg = () =>
    calls.filter((c) => c.path === "/bff/v1/assets/suggestions");
  await act(() => vi.advanceTimersByTimeAsync(300));
  expect(sugg()).toHaveLength(0);
  await act(() => vi.advanceTimersByTimeAsync(150));
  await waitFor(() => expect(sugg().length).toBeGreaterThan(0));
  const list = await screen.findByRole("listbox", { name: "输入建议" });
  expect(within(list).getByRole("group", { name: "数据表" })).toBeVisible();
  expect(within(list).getByRole("group", { name: "列" })).toBeVisible();
  expect(
    within(list).getByRole("option", { name: /生产工单/ }),
  ).toHaveTextContent(TABLE_FQN);
});

it("点击表建议进入表详情；点击列建议进入所属表并带上列名；其他类型以名称搜索（FR-012、Q3、U1）", async () => {
  stubAssets(routes());
  const view = openAssets();
  const box = await screen.findByRole("searchbox", { name: "搜索数据资产" });
  await user().type(box, "wo");
  await act(() => vi.advanceTimersByTimeAsync(450));
  await user().click(await screen.findByRole("option", { name: /wo_no/ }));
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(
    `/assets/table/${TABLE_FQN}`,
  );
  expect(screen.getByLabelText("跳转状态")).toHaveTextContent(
    '"column":"wo_no"',
  );
  view.unmount();

  const calls = stubAssets(routes());
  openAssets();
  const box2 = await screen.findByRole("searchbox", { name: "搜索数据资产" });
  await user().type(box2, "良率");
  await act(() => vi.advanceTimersByTimeAsync(450));
  await user().click(await screen.findByRole("option", { name: /产线良率/ }));
  expect(screen.getByLabelText("当前地址")).toHaveTextContent(/^\/assets$/);
  await waitFor(() =>
    expect(
      calls.some(
        (c) =>
          c.path === "/bff/v1/assets/search" &&
          (c.body as { keyword?: string }).keyword === "产线良率",
      ),
    ).toBe(true),
  );
});

it("搜索范围只列有数据的类型，默认搜索全部；回车后按相关性搜索（FR-004、D4）", async () => {
  const calls = stubAssets(routes());
  openAssets();
  const scope = await screen.findByRole("combobox", { name: "搜索范围" });
  await waitFor(() =>
    expect(
      within(scope)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["全部资产", "数据表", "业务术语"]),
  );
  expect(scope).toHaveValue("");
  const box = screen.getByRole("searchbox", { name: "搜索数据资产" });
  await user().type(box, "工单{Enter}");
  await waitFor(() => {
    const last = calls.filter((c) => c.path === "/bff/v1/assets/search").at(-1)
      ?.body as {
      keyword: string;
      sort: { field: string };
      scope: string | null;
    };
    expect(last.keyword).toBe("工单");
    expect(last.sort.field).toBe("relevance");
    expect(last.scope).toBeNull();
  });
  await user().selectOptions(scope, "数据表");
  await user().type(box, "{Enter}");
  await waitFor(() => {
    const last = calls.filter((c) => c.path === "/bff/v1/assets/search").at(-1)
      ?.body as { scope: string | null };
    expect(last.scope).toBe("table");
  });
});
