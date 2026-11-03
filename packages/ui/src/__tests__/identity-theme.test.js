/* global document, window, Event, HTMLDialogElement */
import { afterEach, expect, it, vi } from "vitest";
import copy from "../../identity/copy.zh-CN.json";

async function mount(
  markup = '<div class="login-pf-page"><div class="card-pf"><h1 id="kc-page-title">验证你的企业身份</h1><form id="kc-form-login"><input name="password" id="password" type="password"></form></div></div>',
) {
  document.body.innerHTML = markup;
  window.CONTEXTURE_LOGIN_COPY = copy;
  await vi.resetModules();
  await import("../../../../extensions/keycloak/themes/contexture/login/resources/js/contexture.js");
  document.dispatchEvent(new Event("DOMContentLoaded"));
}
afterEach(() => {
  document.body.innerHTML = "";
  delete window.CONTEXTURE_LOGIN_COPY;
  vi.restoreAllMocks();
});
it("扩展移动原生表单并保留节点和字段，没有网络提交代理", async () => {
  await mount();
  expect(document.querySelectorAll("#kc-form-login")).toHaveLength(1);
  expect(document.querySelector(".oc-identity--auth #password")).not.toBeNull();
  expect(document.querySelector(".oc-headline")).toHaveTextContent(
    copy.headline.join(""),
  );
  expect(document.querySelector(".login-pf-page")).toBeNull();
  document.dispatchEvent(new Event("DOMContentLoaded"));
  expect(document.querySelectorAll(".oc-identity")).toHaveLength(1);
});
it("缺少原生表单时不破坏身份服务页面", async () => {
  await mount('<div id="native-error">服务提示</div>');
  expect(document.querySelector("#native-error")).toHaveTextContent("服务提示");
  expect(document.querySelector(".oc-identity")).toBeNull();
});
it("账号优先与仅密码的原生流程有对应提示，保留提交字段", async () => {
  await mount(
    '<div class="login-pf-page"><div class="card-pf"><form id="kc-form-login"><input id="username" name="username"><input id="kc-login" name="login" type="submit" value="登录"></form></div></div>',
  );
  expect(document.querySelector(".oc-card-description")).toHaveTextContent(
    "请输入企业账号，继续验证身份。",
  );
  expect(document.querySelector("#kc-login")).toHaveValue("继续");
  expect(document.querySelector("#username")).toHaveAttribute(
    "placeholder",
    "请输入企业账号",
  );
  await mount();
  expect(document.querySelector(".oc-card-description")).toHaveTextContent(
    "请输入密码，完成企业身份验证。",
  );
});
it("本地帮助只打开说明，不读取或提交密码", async () => {
  // jsdom 没有原生 dialog API；真实键盘与遮罩行为另由 Chromium 验证。
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function () {
      this.setAttribute("open", "");
    },
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function () {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    },
  });
  await mount();
  const help = document.querySelector("[data-help]");
  help.click();
  const dialog = document.querySelector("dialog");
  expect(dialog).toHaveAttribute("open");
  expect(dialog).toHaveTextContent(copy.helpDescription);
  dialog.querySelector("button").click();
  expect(dialog).not.toHaveAttribute("open");
  expect(help).toHaveFocus();
});
