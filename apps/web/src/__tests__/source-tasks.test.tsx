import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { SourcesWorkspace } from "../features/sources/SourcesWorkspace";
import { T0, sourcesFixture, stubBff } from "./sources-fixtures";

afterEach(() => vi.unstubAllGlobals());

const meta = sourcesFixture[0]!.pipelines[0]!;
const lineage = {
  kind: "lineage",
  name: "fixture_mes_lineage_IjKl9012",
  fullyQualifiedName: "fixture-mes.fixture_mes_lineage_IjKl9012",
  deployed: true,
  schedule: { cron: null },
  scheduleEnabled: false,
  lastRun: null,
};
const detail = {
  ...sourcesFixture[0],
  pipelines: [meta, lineage],
  description: "",
  connection: {
    hostPort: "mes:3306",
    username: "ro",
    password: "*********",
    database: "mes",
    tls: false,
  },
  scope: { includeViews: true },
};
const NEW = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const OLD = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const runs = [
  {
    runId: NEW,
    pipelineState: "partialSuccess",
    startDate: T0 + 60_000,
    endDate: T0 + 92_000,
    steps: [
      {
        name: "Mysql",
        records: 15,
        updatedRecords: 0,
        warnings: 0,
        errors: 1,
        filtered: 2,
        failures: [{ name: "mes.v_report", error: "permission denied" }],
      },
      {
        name: "OpenMetadata",
        records: 14,
        updatedRecords: 0,
        warnings: 0,
        errors: 0,
        filtered: 0,
        failures: [],
      },
    ],
  },
  {
    runId: OLD,
    pipelineState: "success",
    startDate: T0,
    endDate: T0 + 25_000,
    steps: [],
  },
];
const base = "/bff/v1/sources/fixture-mes/pipelines";

function open(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/sources/*" element={<SourcesWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );
}

function routes(extra: Parameters<typeof stubBff>[0] = []) {
  return stubBff([
    { path: "/bff/v1/sources", body: { data: sourcesFixture } },
    { path: "/bff/v1/sources/fixture-mes", body: detail },
    { path: `${base}/metadata/runs`, body: { data: runs } },
    { path: `${base}/lineage/runs`, body: { data: [] } },
    {
      path: `${base}/metadata/logs/last`,
      body: { runId: NEW, logs: "INFO 采集完成（夹具）" },
    },
    ...extra,
  ]);
}

it("任务列表按 pipelines 渲染两条任务；运行记录列与筛选只作用于当前任务", async () => {
  const calls = routes();
  open("/sources/fixture-mes?tab=tasks");
  const tasks = await screen.findByRole("table", { name: "采集任务" });
  expect(within(tasks).getAllByRole("row")).toHaveLength(3);
  expect(within(tasks).getByText("视图血缘").closest("tr")).toHaveTextContent(
    "待首次采集",
  );
  await userEvent.click(within(tasks).getByRole("button", { name: meta.name }));
  const table = await screen.findByRole("table", { name: "运行记录" });
  expect(
    within(table)
      .getAllByRole("columnheader")
      .map((h) => h.textContent),
  ).toEqual(["开始时间", "状态", "耗时", "运行编号", "操作"]);
  expect(within(table).getAllByRole("row")[1]).toHaveTextContent("部分成功");
  expect(within(table).getAllByRole("row")[1]).toHaveTextContent("32 秒");
  expect(within(table).getAllByRole("row")[1]).toHaveTextContent("aaaaaaaa");
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "筛选运行状态" }),
    "success",
  );
  await waitFor(() =>
    expect(
      calls.some(
        (c) => c.path === `${base}/metadata/runs` && c.method === "GET",
      ),
    ).toBe(true),
  );
  expect(
    calls.every((c) => !c.path.includes("/lineage/runs") || c.method === "GET"),
  ).toBe(true);
});

it("运行详情：步骤统计与失败对象；最近一次运行显示日志，更早的注明", async () => {
  routes();
  open("/sources/fixture-mes?tab=tasks&task=metadata");
  const table = await screen.findByRole("table", { name: "运行记录" });
  await userEvent.click(
    within(table).getAllByRole("button", { name: "查看运行" })[0]!,
  );
  const dialog = screen.getByRole("dialog", { name: "运行详情" });
  const steps = within(dialog).getByRole("table", { name: "步骤统计" });
  expect(within(steps).getByText("Mysql").closest("tr")).toHaveTextContent(
    "Mysql150012",
  );
  expect(dialog).toHaveTextContent("mes.v_report");
  expect(await within(dialog).findByLabelText("运行日志")).toHaveTextContent(
    "采集完成（夹具）",
  );
  expect(
    within(dialog).getByRole("button", { name: "立即运行" }),
  ).toBeVisible();
  await userEvent.click(within(dialog).getByRole("button", { name: "关闭" }));
  await userEvent.click(
    within(table).getAllByRole("button", { name: "查看运行" })[1]!,
  );
  const older = screen.getByRole("dialog", { name: "运行详情" });
  expect(older).toHaveTextContent("OpenMetadata 仅提供最近一次运行的日志");
  expect(within(older).queryByLabelText("运行日志")).not.toBeInTheDocument();
});

it("暂停调度需确认；运行中禁用立即运行；立即运行冲突显示真实错误", async () => {
  const calls = routes([
    {
      method: "PUT",
      path: `${base}/metadata/schedule`,
      body: { ...meta, scheduleEnabled: false },
    },
    {
      method: "POST",
      path: `${base}/metadata/trigger`,
      status: 409,
      body: {
        code: "source.pipeline_in_flight",
        message: "该任务已有排队中或运行中的运行",
        trace_id: "e".repeat(32),
      },
    },
  ]);
  open("/sources/fixture-mes?tab=tasks&task=metadata");
  await screen.findByRole("table", { name: "运行记录" });
  await userEvent.click(screen.getByRole("button", { name: "暂停调度" }));
  const confirm = screen.getByRole("dialog", { name: "暂停定时采集？" });
  await userEvent.click(
    within(confirm).getByRole("button", { name: "确认暂停" }),
  );
  await waitFor(() =>
    expect(
      calls.some(
        (c) =>
          c.method === "PUT" &&
          c.body &&
          (c.body as { enabled: boolean }).enabled === false,
      ),
    ).toBe(true),
  );
  await userEvent.click(screen.getByRole("button", { name: "立即运行" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "该任务已有排队中或运行中的运行",
  );
});

it("手动任务显示配置调度；调度详情的 DAG 标识等于任务名", async () => {
  routes();
  open("/sources/fixture-mes?tab=tasks&task=lineage");
  await screen.findByRole("table", { name: "运行记录" });
  expect(screen.getByRole("button", { name: "配置调度" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "调度详情" }));
  expect(screen.getByRole("dialog", { name: "调度任务" })).toHaveTextContent(
    lineage.name,
  );
});

it("排队中的运行禁用立即运行", async () => {
  stubBff([
    { path: "/bff/v1/sources", body: { data: sourcesFixture } },
    {
      path: "/bff/v1/sources/fixture-mes",
      body: {
        ...detail,
        pipelines: [
          { ...meta, lastRun: { ...runs[1], pipelineState: "queued" } },
        ],
      },
    },
    {
      path: `${base}/metadata/runs`,
      body: { data: [{ ...runs[1], pipelineState: "queued" }] },
    },
  ]);
  open("/sources/fixture-mes?tab=tasks&task=metadata");
  await screen.findByRole("table", { name: "运行记录" });
  expect(screen.getByRole("button", { name: "立即运行" })).toBeDisabled();
});
