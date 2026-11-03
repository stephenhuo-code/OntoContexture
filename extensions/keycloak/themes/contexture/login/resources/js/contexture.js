/* global document, window */
// 渐进增强官方主题：只装配品牌布局，原生表单节点与身份服务脚本完整保留。
(() => {
  function start() {
    const copy = window.CONTEXTURE_LOGIN_COPY;
    const original = document.querySelector(".card-pf");
    if (!copy || !original || document.querySelector(".oc-identity")) return;
    const nativeTitle = original.querySelector("#kc-page-title");
    const nativeWrapper = original.closest(".login-pf-page");
    const root = document.createElement("div");
    root.className = "oc-identity oc-identity--auth";
    root.lang = "zh-CN";
    root.innerHTML = `<header class="oc-header"><div class="oc-brand"><span class="oc-mark" aria-hidden="true"></span><span class="oc-name"></span><span class="oc-en"></span></div><span class="oc-language"></span></header>
      <main class="oc-hero"><div class="oc-hero-inner"><section class="oc-intro"><p class="oc-eyebrow"></p><h1 class="oc-headline"><span></span><br><span></span></h1><p class="oc-description"><span></span><br><span></span></p><div class="oc-principles"></div></section><section class="oc-card"><div class="oc-auth-heading"></div><h2 class="oc-title"></h2><p class="oc-card-description"></p><div data-native-form></div><p class="oc-note"></p><div class="oc-assist"><span></span><button type="button" class="oc-help" data-help></button></div></section></div></main>
      <section class="oc-features"><div class="oc-features-inner"></div></section><footer class="oc-footer"><span></span><span></span></footer>`;
    const put = (selector, text) => {
      root.querySelector(selector).textContent = text;
    };
    put(".oc-name", copy.brand);
    put(".oc-en", copy.name);
    put(".oc-language", copy.language);
    put(".oc-eyebrow", copy.eyebrow);
    root.querySelectorAll(".oc-headline span").forEach((node, index) => {
      node.textContent = copy.headline[index];
    });
    root.querySelectorAll(".oc-description span").forEach((node, index) => {
      node.textContent = copy.description[index];
    });
    for (const text of copy.principles) {
      const item = document.createElement("span");
      item.textContent = text;
      root.querySelector(".oc-principles").append(item);
    }
    for (const feature of copy.features) {
      const item = document.createElement("article");
      item.className = "oc-feature";
      const icon = document.createElement("span");
      icon.className = "oc-feature-icon oc-feature-icon--" + feature.icon;
      icon.setAttribute("aria-hidden", "true");
      const content = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = feature.title;
      const description = document.createElement("p");
      description.textContent = feature.description;
      content.append(title, description);
      item.append(icon, content);
      root.querySelector(".oc-features-inner").append(item);
    }
    root.querySelector(".oc-card").setAttribute("aria-label", copy.cardLabel);
    put(".oc-auth-heading", copy.identityHeading);
    const form = original.querySelector("#kc-form-login");
    const username = original.querySelector('#username:not([type="hidden"])');
    const password = original.querySelector("#password");
    put(
      ".oc-title",
      form
        ? copy.identityTitle
        : nativeTitle?.textContent.trim() || copy.identityTitle,
    );
    put(
      ".oc-card-description",
      username && !password
        ? copy.accountStep
        : password && !username
          ? copy.passwordStep
          : copy.identityDescription,
    );
    username?.setAttribute("placeholder", copy.accountPlaceholder);
    password?.setAttribute("placeholder", copy.passwordPlaceholder);
    if (username && !password)
      original.querySelector("#kc-login")?.setAttribute("value", copy.next);
    put(".oc-note", copy.identityNote);
    put(".oc-assist span", copy.assistance);
    put("[data-help]", copy.helpAction);
    root.querySelectorAll(".oc-footer span").forEach((node, index) => {
      node.textContent = index === 0 ? copy.footer : copy.assurance;
    });
    // 移动同一节点，不克隆、读取或提交密码，也不改 action / hidden fields。
    root.querySelector("[data-native-form]").append(original);
    document.body.append(root);
    nativeWrapper?.remove();
    const dialog = document.createElement("dialog");
    dialog.className = "oc-help-dialog";
    dialog.setAttribute("aria-labelledby", "oc-help-title");
    const title = document.createElement("h2");
    title.id = "oc-help-title";
    title.textContent = copy.helpTitle;
    const description = document.createElement("p");
    description.textContent = copy.helpDescription;
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = copy.helpClose;
    dialog.append(title, description, close);
    document.body.append(dialog);
    const help = root.querySelector("[data-help]");
    help.addEventListener("click", () => dialog.showModal());
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => help.focus());
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
