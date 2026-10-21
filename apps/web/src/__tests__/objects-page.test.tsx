import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ObjectsPage } from "../pages/ObjectsPage";

const VIEW = {
  object_type: {
    type_uri: "urn:ctx:object:quality:Equipment",
    name: "Equipment",
    display_name: "设备",
    version: "0.2",
    attributes: [
      { name: "code", data_type: "string", required: true, data_level: 1 },
      { name: "model", data_type: "string", required: false, data_level: 2 },
    ],
  },
  items: [
    {
      object_uri: "urn:ctx:obj:local:Equipment:CNC-01",
      type_uri: "urn:ctx:object:quality:Equipment",
      attributes: { code: "CNC-01", model: "Mazak" },
      source: "mcp:list_objects",
    },
    {
      object_uri: "urn:ctx:obj:local:Equipment:CNC-02",
      type_uri: "urn:ctx:object:quality:Equipment",
      attributes: { code: "CNC-02", model: "DMG" },
      source: "mcp:list_objects",
    },
  ],
  trace_id: "4bf92f3577b34da6a3ce929d0e0e4736",
};

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async (_request: Request) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/objects/equipment"]}>
      <Routes>
        <Route path="/objects/:typeKey" element={<ObjectsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("示例页面：对象定义与对象列表", () => {
  it("显示对象定义表（来自 OM）", async () => {
    mockFetch(200, VIEW);
    renderPage();
    expect(
      await screen.findByRole("heading", { name: /设备/ }),
    ).toBeInTheDocument();
    const definition = screen.getByRole("table", { name: "对象定义" });
    expect(within(definition).getByText("code")).toBeInTheDocument();
    expect(
      within(definition).getByText("urn:ctx:object:quality:Equipment"),
    ).toBeInTheDocument();
  });

  it("显示设备列表（来自 Doris，经 AI 网关）", async () => {
    mockFetch(200, VIEW);
    renderPage();
    const list = await screen.findByRole("table", { name: "对象列表" });
    expect(within(list).getAllByRole("row")).toHaveLength(3); // 表头 + 2 行
    expect(within(list).getByText("CNC-02")).toBeInTheDocument();
    expect(screen.getByText(VIEW.trace_id)).toBeInTheDocument();
  });

  it("请求 bff 的示例查询接口", async () => {
    const fetchMock = mockFetch(200, VIEW);
    renderPage();
    await screen.findByRole("table", { name: "对象列表" });
    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(new URL(request.url).pathname).toBe(
      "/bff/v1/object-types/equipment/objects",
    );
  });

  it("接口出错时显示统一错误信息", async () => {
    mockFetch(502, {
      code: "upstream.unavailable",
      message: "AI 网关不可用",
      trace_id: "abc123",
    });
    renderPage();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("AI 网关不可用");
    expect(alert).toHaveTextContent("upstream.unavailable");
    expect(alert).toHaveTextContent("abc123");
  });
});
