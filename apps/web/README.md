# apps/web/

织境 Web（React），打包为 nginx 静态资源镜像独立部署，浏览器业务请求统一经 BFF。
架构采用 [ADR-0003](../../docs/adr/0003-前端架构与管理端策略.md) 2026-11-01 确认的方案 B：

- 织境维护主导航、账号、设计系统、资产 / 治理 / 审批 / 上下文页面与轻量页面助手。
- 007 通过官方 `OmnigentApp` 嵌入完整工作台，产物从 `third_party/omnigent/src/` 锁定版本构建；不复制上游 UI 组件。
- 页面助手经 BFF 优先复用官方客户端 / 已发布 API，与工作台关联同一个服务端会话；业务结果组件在织境侧维护。
- 必要定制依次使用配置、官方扩展点和最小补丁，补丁按 [ADR-0002](../../docs/adr/0002-Agent框架采用Omnigent.md) 登记。

当前 004 实现外壳与公共组件；正式 Agent 集成归 007，安全沙箱与终端归 012。
实际嵌入、身份与会话联动尚待验证，见 [004 plan](../../specs/004-web-shell/plan.md) 和
[嵌入验证契约](../../specs/004-web-shell/contracts/embed-readiness.md)。


## 页面接入与演练

依赖固定为 React 18.3.1、React Router 7.18.2、Vite 8.3.4。亮色令牌和基础组件来自 `@contexture/ui`，
自有简体中文统一放 `src/i18n/zh-CN.ts`。原型只作设计依据，不复用其代码。

```bash
pnpm --filter @contexture/web dev
pnpm --filter @contexture/web test:coverage
pnpm --filter @contexture/ui test:coverage
pnpm --filter @contexture/web build
pnpm e2e:ui
```

Web 允许 admin 或 ai-engineer，业务用户单独不准入。首次到站按登录按钮进入既有企业认证。
退出只删除织境会话，不调用 IdP logout；成功后停留登录入口，主动再次登录要求 Keycloak 重新认证，本地测试账号需输入密码；正常刷新 / 续期继续保持登录。
`/objects/equipment` 是受保护的旧设备回归地址，不在业务导航中。

标准生产构建访问 `/__dev/ui` 显示不存在。开发演练先在 `http://localhost:8080/home` 真实登录，
再用同一浏览器打开 `http://localhost:5173/__dev/ui`；5173 通过 Vite 代理 BFF，沿用 localhost Cookie，
不新增 IdP 回调。示例数据均标为开发演示，不对接业务接口。

按 `src/pages/UiExamplesPage.tsx` 练习新增内容页：

1. 新内容组件仅返回内容，复用 `Panel` / `PageState`，不另建 Router、会话 Provider 或导航。
2. 在 `App.tsx` 现有受保护的 AppShell 子路由注册页面；公共登录失败页仍在门禁之外。
3. 正式菜单项在 `layout/navigation.ts` 定义名称、路径、模块和可用状态；页头和高亮由路径派生。
   有界面的新特性先按宪法走 HTML 原型与 spec；不要为未交付业务生成假目录。
4. 在 `zh-CN.ts` 增加文案，复用现有身份，不发起第二次 Me 请求。
5. 空内容写下一步动作；错误可以重试；无权限不能暗示重试获权；未开放提供返回首页。
6. 先写受保护路由、加载 / 故障恢复及长文案行为测试，再实现；用两个桌面尺寸和键盘复验。

开发示例的“独立页面接入演示”是上述内容组件的最小例子：添加演示记录仅更新本地状态，
它与其他示例共用同一 Shell、页头和 PageState。以上由开发侧验证并提供工程证据，不要求用户操作开发示例。用户仅验收正式产品页面，见 [004 用户验收](../../specs/004-web-shell/acceptance.md)。
