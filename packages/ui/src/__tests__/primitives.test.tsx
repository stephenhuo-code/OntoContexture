import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button, Panel, StatusBadge, TextInput, Tooltip } from "../index";

describe("共享基础组件", () => {
  it("支持主次操作及键盘焦点", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    render(
      <>
        <Button onClick={submit}>保存</Button>
        <Button variant="secondary">取消</Button>
      </>,
    );
    await user.tab();
    expect(screen.getByRole("button", { name: "保存" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(submit).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "取消" })).toHaveClass(
      "ctx-button--secondary",
    );
  });

  it("disabled 和 busy 都阻止重复操作", async () => {
    const click = vi.fn();
    const view = render(
      <Button busy onClick={click}>
        提交
      </Button>,
    );
    const button = screen.getByRole("button", { name: "提交" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    fireEvent.click(button);
    view.rerender(
      <Button disabled onClick={click}>
        提交
      </Button>,
    );
    fireEvent.click(button);
    expect(click).not.toHaveBeenCalled();
    view.rerender(<Button onClick={click}>提交</Button>);
    await userEvent.click(button);
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("输入框有标签并保留长中文内容", async () => {
    const text = "质量治理的中文内容".repeat(12);
    render(<TextInput label="名称" defaultValue={text} />);
    expect(screen.getByRole("textbox", { name: "名称" })).toHaveValue(text);
    await userEvent.clear(screen.getByLabelText("名称"));
    await userEvent.type(screen.getByLabelText("名称"), "新名称");
    expect(screen.getByLabelText("名称")).toHaveValue("新名称");
  });

  it("面板与状态有可读文字", () => {
    render(
      <Panel title="覆盖情况">
        <StatusBadge tone="warning">尚未接入</StatusBadge>
      </Panel>,
    );
    expect(screen.getByRole("heading", { name: "覆盖情况" })).toBeVisible();
    expect(screen.getByText("尚未接入")).toBeVisible();
  });

  it("提示支持键盘聚焦和 Escape", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="当前登录账号">
        <Button>账号</Button>
      </Tooltip>,
    );
    await user.tab();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "当前登录账号",
    );
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("提示支持悬停", async () => {
    render(
      <Tooltip content="完整中文入口名称">
        <Button>入口</Button>
      </Tooltip>,
    );
    await userEvent.hover(screen.getByRole("button", { name: "入口" }));
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "完整中文入口名称",
    );
  });
});
