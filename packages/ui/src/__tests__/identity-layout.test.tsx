import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import copy from "../../identity/copy.zh-CN.json";
import { IdentityLayout, IdentityHelp } from "../components/IdentityLayout";

it("身份布局支持正常与恢复内容，不包含原型控制器", () => {
  const view = render(
    <IdentityLayout copy={copy}>
      <h2>登录内容</h2>
    </IdentityLayout>,
  );
  expect(
    screen.getByRole("region", { name: copy.cardLabel }),
  ).toHaveTextContent("登录内容");
  expect(screen.getByText(copy.features[0].title)).toBeVisible();
  view.rerender(
    <IdentityLayout copy={copy} state>
      <h2>恢复内容</h2>
    </IdentityLayout>,
  );
  expect(
    screen.getByRole("region", { name: copy.cardLabel }),
  ).toHaveTextContent("恢复内容");
  expect(screen.queryByText("设计预览")).not.toBeInTheDocument();
});
it("帮助对话框支持键盘打开、关闭和焦点恢复", async () => {
  render(<IdentityHelp copy={copy} />);
  const button = screen.getByRole("button", { name: copy.helpAction });
  button.focus();
  await userEvent.keyboard("{Enter}");
  expect(
    await screen.findByRole("dialog", { name: copy.helpTitle }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: copy.helpClose }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(button).toHaveFocus();
});
