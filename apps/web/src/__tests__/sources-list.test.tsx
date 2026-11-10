import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { renderQ } from "./query-wrapper";
import { afterEach, expect, it, vi } from "vitest";
import { AssetsWorkspace } from "../features/assets/AssetsWorkspace";
import { sourcesFixture, stubBff } from "./sources-fixtures";

afterEach(() => vi.unstubAllGlobals());

function open(path = "/assets/sources") {
  return renderQ(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/assets/*" element={<AssetsWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );
}

it("统计卡按 BFF 数据计算：已配置 2/3、20 张表、132 个字段、1 项需要关注", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: sourcesFixture } }]);
  open();
  const stats = await screen.findByRole("region", { name: "数据源汇总" });
  expect(
    within(stats).getByText("已配置数据源").closest("div"),
  ).toHaveTextContent("2/ 3");
  expect(within(stats).getByText("已采集表").closest("div")).toHaveTextContent(
    "20张",
  );
  expect(
    within(stats).getByText("字段元数据").closest("div"),
  ).toHaveTextContent("132个");
  expect(within(stats).getByText("需要关注").closest("div")).toHaveTextContent(
    "1项",
  );
  const table = screen.getByRole("table", { name: "数据源列表" });
  expect(within(table).getAllByRole("row")).toHaveLength(4);
  expect(within(table).getByText("夹具 QMS").closest("tr")).toHaveTextContent(
    "部分成功",
  );
  expect(within(table).getByText("夹具 ERP").closest("tr")).toHaveTextContent(
    "待配置",
  );
  expect(within(table).getByText("夹具 MES").closest("tr")).toHaveTextContent(
    "每天 02:00",
  );
});

it("空列表显示空状态，不出现任何示例数据源", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: [] } }]);
  open();
  expect(await screen.findByText("还没有数据源")).toBeVisible();
  expect(
    screen.queryByRole("table", { name: "数据源列表" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText(/mock-|MES 生产执行系统/)).not.toBeInTheDocument();
});

it("BFF 不可用时显示真实错误与重试，不回退示例数据", async () => {
  stubBff([
    {
      path: "/bff/v1/sources",
      status: 502,
      body: {
        code: "upstream.unavailable",
        message: "OpenMetadata 不可用",
        trace_id: "c".repeat(32),
      },
    },
  ]);
  open();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("OpenMetadata 不可用");
  expect(alert).toHaveTextContent("c".repeat(32));
  expect(screen.getByRole("button", { name: "重试" })).toBeVisible();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("搜索与状态筛选", async () => {
  stubBff([{ path: "/bff/v1/sources", body: { data: sourcesFixture } }]);
  open();
  const table = await screen.findByRole("table", { name: "数据源列表" });
  await userEvent.type(
    screen.getByRole("searchbox", { name: "搜索数据源" }),
    "qms",
  );
  expect(within(table).getAllByRole("row")).toHaveLength(2);
  await userEvent.clear(screen.getByRole("searchbox", { name: "搜索数据源" }));
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "按状态筛选" }),
    "draft",
  );
  expect(within(table).getAllByRole("row")).toHaveLength(2);
  expect(within(table).getByText("夹具 ERP")).toBeVisible();
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "按状态筛选" }),
    "paused",
  );
  expect(screen.getByText("没有匹配的数据源")).toBeVisible();
});
