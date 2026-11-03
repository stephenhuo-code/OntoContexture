import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { PageState } from "../index";

it.each([
  "loading",
  "empty",
  "error",
  "forbidden",
  "not_open",
  "not_found",
] as const)("%s 状态展示独立文案", (kind) => {
  render(
    <PageState kind={kind} title={`状态 ${kind}`} description="说明当前情况" />,
  );
  expect(screen.getByRole("heading", { name: `状态 ${kind}` })).toBeVisible();
  expect(screen.getByText("说明当前情况")).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("重试期间不重复提交，失败后能再次重试并恢复", async () => {
  const retry = vi
    .fn()
    .mockRejectedValueOnce(Error("temporary"))
    .mockResolvedValue(undefined);
  function Example() {
    const [state, setState] = useState("error");
    if (state === "ready") return <p>内容已恢复</p>;
    return (
      <PageState
        kind={state === "busy" ? "loading" : "error"}
        title="读取未完成"
        actionLabel="重试"
        busy={state === "busy"}
        action={() => {
          setState("busy");
          void retry().then(
            () => setState("ready"),
            () => setState("error"),
          );
        }}
      />
    );
  }
  render(<Example />);
  await userEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(screen.getByRole("button", { name: "重试" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(await screen.findByText("内容已恢复")).toBeVisible();
  expect(retry).toHaveBeenCalledTimes(2);
});

it.each(["forbidden", "not_open", "not_found"] as const)(
  "%s 提供返回入口",
  async (kind) => {
    const home = vi.fn();
    render(
      <PageState
        kind={kind}
        title="当前页面不可用"
        actionLabel="返回首页"
        action={home}
      />,
    );
    expect(
      screen.queryByRole("button", { name: "重试" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "返回首页" }));
    expect(home).toHaveBeenCalledOnce();
  },
);

it("仅展示安全格式的诊断标识", () => {
  const trace = "a".repeat(32);
  const view = render(<PageState kind="error" title="失败" traceId={trace} />);
  expect(screen.getByText(`诊断编号：${trace}`)).toBeVisible();
  view.rerender(<PageState kind="error" title="失败" traceId="token:secret" />);
  expect(screen.queryByText(/token:secret/)).not.toBeInTheDocument();
});

it("忙碌操作不能重复触发", () => {
  const action = vi.fn();
  render(
    <PageState
      kind="loading"
      title="加载中"
      actionLabel="继续"
      action={action}
      busy
    />,
  );
  expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  expect(screen.getByRole("button", { name: "继续" })).toBeDisabled();
});
