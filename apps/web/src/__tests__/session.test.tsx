import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../App";

const USER = {
  tenant_id: "local",
  user_id: "subject-1",
  display_name: "真实工程师",
  roles: ["ai-engineer"],
};
function response(status: number, body: unknown = USER) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
function open(path = "/home") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}
afterEach(() => vi.unstubAllGlobals());
it("身份检查完成后显示真实姓名及首页", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response(200)),
  );
  open();
  expect(
    await screen.findByRole("heading", { name: /你好，真实工程师/ }),
  ).toBeVisible();
});
it.each([undefined, null, ""])(
  "姓名 %s 时回退用户 ID，缺省角色不伪造",
  async (display_name) => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        response(200, {
          tenant_id: "local",
          user_id: "subject-1",
          display_name,
        }),
      ),
    );
    open();
    expect(
      await screen.findByRole("heading", { name: /你好，subject-1/ }),
    ).toBeVisible();
    expect(screen.queryByText("AI 工程师")).not.toBeInTheDocument();
  },
);
it("401 显示登录入口而不自动跳 SSO", async () => {
  const fetch = vi.fn(async () => response(401, {}));
  vi.stubGlobal("fetch", fetch);
  open();
  expect(
    await screen.findByRole("button", { name: "使用企业账号登录" }),
  ).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("403 无权限可退出，无登录循环或重试获权", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response(403, {})),
  );
  open();
  expect(
    await screen.findByRole("heading", { name: "无权访问织境" }),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "退出" })).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "使用企业账号登录" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "重试" }),
  ).not.toBeInTheDocument();
});
it.each([500, 502])("%s 故障可重试恢复，不能当作未登录", async (status) => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(response(status, {}))
    .mockResolvedValue(response(200));
  vi.stubGlobal("fetch", fetch);
  open();
  expect(
    await screen.findByRole("heading", { name: "暂时无法确认身份" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "使用企业账号登录" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(
    await screen.findByRole("heading", { name: /你好，真实工程师/ }),
  ).toBeVisible();
});
it("退出失败保留可重试动作，204 后清除旧用户且不自动 SSO", async () => {
  let attempts = 0;
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: Request | string) => {
      const path = new URL(
        typeof input === "string" ? input : input.url,
        "http://localhost",
      ).pathname;
      calls.push(path);
      if (path.endsWith("/logout"))
        return ++attempts === 1
          ? response(500, {})
          : new Response(null, { status: 204 });
      return response(200);
    }),
  );
  open();
  await screen.findByRole("heading", { name: /你好，真实工程师/ });
  await userEvent.click(screen.getByRole("button", { name: "退出" }));
  expect(await screen.findByText("退出未完成，请重试。")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "退出" }));
  expect(
    await screen.findByRole("button", { name: "使用企业账号登录" }),
  ).toBeVisible();
  expect(
    screen.queryByText("真实工程师", { exact: true }),
  ).not.toBeInTheDocument();
  expect(calls.filter((p) => p.includes("/auth/login"))).toHaveLength(0);
  fireEvent.focus(window);
  expect(calls.filter((p) => p === "/bff/v1/me")).toHaveLength(1);
});
it("重新聚焦时后台核验：页面保留但不可操作，换用户后旧页面状态清除", async () => {
  let finish: (r: Response) => void = () => {};
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(response(200))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    );
  vi.stubGlobal("fetch", fetch);
  open();
  const old = await screen.findByRole("heading", { name: /你好，真实工程师/ });
  fireEvent.focus(window);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  // 核验期间：提示正在确认身份，旧用户页面不可操作（inert），不切换为整页加载
  expect(screen.getByRole("status", { name: "正在确认身份" })).toBeVisible();
  expect(old.closest("[inert]")).not.toBeNull();
  await act(async () =>
    finish(
      response(200, {
        ...USER,
        user_id: "subject-2",
        display_name: "下一位工程师",
      }),
    ),
  );
  const next = await screen.findByRole("heading", {
    name: /你好，下一位工程师/,
  });
  expect(next.closest("[inert]")).toBeNull();
  expect(old).not.toBeInTheDocument();
});
it("同一用户重新聚焦：核验后页面状态保留（打开的弹窗与已填内容不丢）", async () => {
  let finish: (r: Response) => void = () => {};
  let meCalls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (req: Request) => {
      const path = new URL(req.url, "http://localhost").pathname;
      if (path === "/bff/v1/me") {
        meCalls += 1;
        if (meCalls === 1) return response(200);
        return new Promise<Response>((resolve) => {
          finish = resolve;
        });
      }
      return response(200, { data: [] });
    }),
  );
  open("/assets/sources");
  await userEvent.click(
    await screen.findByRole("button", { name: "添加数据源" }),
  );
  const dialog = screen.getByRole("dialog", { name: "添加数据源" });
  await userEvent.type(within(dialog).getByLabelText("显示名称 *"), "华东 MES");
  fireEvent.focus(window);
  await waitFor(() => expect(meCalls).toBe(2));
  await act(async () => finish(response(200)));
  await waitFor(() =>
    expect(
      screen.queryByRole("status", { name: "正在确认身份" }),
    ).not.toBeInTheDocument(),
  );
  const still = screen.getByRole("dialog", { name: "添加数据源" });
  expect(within(still).getByLabelText("显示名称 *")).toHaveValue("华东 MES");
  expect(still.closest("[inert]")).toBeNull();
});
it("页面卸载取消身份请求，迟到响应不能污染下一次身份", async () => {
  let signal: AbortSignal | undefined;
  let finish: (value: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) => {
      signal = request.signal;
      return new Promise<Response>((resolve) => {
        finish = resolve;
      });
    }),
  );
  const first = open();
  await waitFor(() => expect(signal).toBeDefined());
  first.unmount();
  expect(signal?.aborted).toBe(true);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response(200, { ...USER, display_name: "新用户" })),
  );
  open();
  expect(
    await screen.findByRole("heading", { name: /你好，新用户/ }),
  ).toBeVisible();
  await act(async () => finish(response(200, USER)));
  expect(screen.getByRole("heading", { name: /你好，新用户/ })).toBeVisible();
});
it("公共登录失败页不依赖 Me，只渲染安全恢复说明", async () => {
  const fetch = vi.fn(async () => {
    throw Error("offline");
  });
  vi.stubGlobal("fetch", fetch);
  open(
    "/auth/error?reason=cancelled&code=PRIVATE&state=PRIVATE&error_description=PRIVATE&return_to=https%3A%2F%2Fevil&trace_id=secret",
  );
  expect(
    await screen.findByRole("heading", { name: "登录已取消" }),
  ).toBeVisible();
  expect(screen.queryByText(/PRIVATE|secret/)).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "重新登录" })).toHaveAttribute(
    "href",
    "/bff/v1/auth/login?return_to=%2Fhome",
  );
  expect(fetch).not.toHaveBeenCalled();
});

it("长账号可展开完整身份", async () => {
  const name = "很长的中文姓名".repeat(12);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response(200, { ...USER, display_name: name })),
  );
  open();
  await screen.findByRole("heading", { name: new RegExp("你好，" + name) });
  await userEvent.click(screen.getByLabelText(new RegExp("当前账号：")));
  expect(screen.getByText("用户 ID：subject-1")).toBeVisible();
});
