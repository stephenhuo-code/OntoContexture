import { afterEach, expect, it, vi } from "vitest";
import {
  listSources,
  listRuns,
  triggerPipeline,
} from "../features/sources/api";

afterEach(() => vi.unstubAllGlobals());

function respond(status: number, body: unknown) {
  return vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
}

it("数据源列表同源请求 BFF，原样返回服务端数据", async () => {
  const fetchMock = respond(200, { data: [] });
  vi.stubGlobal("fetch", fetchMock);
  expect(await listSources()).toEqual([]);
  const sent = fetchMock.mock.calls[0]?.[0] as unknown as Request;
  expect(new URL(sent.url).pathname).toBe("/bff/v1/sources");
  expect(sent.credentials).toBe("same-origin");
});

it("BFF 返回 502 时抛出带错误码与 trace_id 的错误，不返回任何数据（宪法 v2.2.0）", async () => {
  vi.stubGlobal(
    "fetch",
    respond(502, {
      code: "upstream.unavailable",
      message: "OpenMetadata 不可用",
      trace_id: "a".repeat(32),
    }),
  );
  await expect(listSources()).rejects.toMatchObject({
    status: 502,
    error: { code: "upstream.unavailable", trace_id: "a".repeat(32) },
  });
});

it("网络失败抛出状态 0，不回退示例数据", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => {
      throw Error("offline");
    }),
  );
  await expect(listRuns("mock-mes", "metadata")).rejects.toMatchObject({
    status: 0,
  });
});

it("立即运行冲突时保留 source.pipeline_in_flight", async () => {
  vi.stubGlobal(
    "fetch",
    respond(409, {
      code: "source.pipeline_in_flight",
      message: "该任务已有排队中或运行中的运行",
      trace_id: "b".repeat(32),
    }),
  );
  await expect(triggerPipeline("mock-mes", "lineage")).rejects.toMatchObject({
    status: 409,
    error: { code: "source.pipeline_in_flight" },
  });
});
