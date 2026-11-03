# Quickstart: 004 开发与工程验证指南

本指南由开发人员执行，不作为用户逐项验收清单。用户只需按 [用户验收文档](acceptance.md) 使用正式页面。

实现后的开发 / 验证命令见下文；实测结果见 [validation.md](evidence/validation.md)，
负责人手动验收见 [acceptance.md](acceptance.md)。命令列表本身不表示验收通过。

## 1. 前置条件

- 现有开发工具与 001 的本地环境；使用仓库原有 uv / pnpm / Docker / kind，不另外搭一套身份服务。
- 本地身份服务可用；Web 成功路径使用已配置管理员或 AI 工程师，业务用户用于拒绝验证。
  不为本次验证改动 Paperclip 或共享 realm 中其他应用的配置。
- 新角色组合优先在自动化测试的临时 Keycloak 夹具中准备；不在共享环境任意增删真实用户角色。
- 旧设备回归需要既有 OM / Doris 与种子数据；外壳自身的导航和占位不依赖它们。

在仓库根执行已有环境安装与基础检查：

```bash
uv sync --all-packages
pnpm install --frozen-lockfile
make lint
make test
pnpm --filter @contexture/ts-api check
pnpm --filter @contexture/web test
pnpm --filter @contexture/web build
```

预期：锁文件与生成类型一致，所有检查通过。实测记录单独列在 evidence。

## 2. UI 包与覆盖率

```bash
pnpm --filter @contexture/ui test
pnpm --filter @contexture/ui test:coverage
pnpm --filter @contexture/web test:coverage
```

预期：组件矩阵与会话 / 导航用例通过，新增与修改行达到 ≥80% 门槛；没有复制上游 UI / 原型代码。
先运行 make test 生成 coverage.json，再运行 make coverage-check；CI 与本地均检查变更可执行行 ≥80%。

## 3. 真实身份与会话集成

```bash
uv run pytest services/bff/tests/integration/test_auth_flow.py -q
uv run pytest services/bff/tests/unit/test_auth_api.py services/bff/tests/contract -q
uv run pytest packages/py-core/tests/test_auth.py -q
```

预期：真实 Keycloak / PostgreSQL 集成通过；Web 允许 admin / ai-engineer，拒绝 business-only / no-role；
混合角色按 OR 判定。网络 / IdP 故障与 invalid_grant 的分支分别验证，不能统一变 401。
退出本地会话与 Cookie 后，旧 Cookie 不可访问，验证过程中不调用 IdP 全局 logout 或任何 Paperclip 接口。
临时身份、证书、容器夹具复用当前测试支持，不把 token 打进命令行或日志。

## 4. 开发人员的浏览器与组件检查

已有集群入口通常为 `http://localhost:8080`；前端开发可使用：

```bash
pnpm --filter @contexture/web dev
```

预期 Vite 本地入口代理 `/bff` 到现有平台。开发示例使用同一浏览器先在 `http://localhost:8080/home`
完成真实登录，再打开 `http://localhost:5173/__dev/ui`；两个地址均用 localhost，复用同主机 Cookie，
不新增 5173 的 IdP 回调。生产入口 `/__dev/ui` 必须显示不存在。

在部署入口执行：

1. 未登录访问 `/home`，进入企业登录流程；用工程师账号登录后显示真实身份与首页。
2. 按一级顺序进入新建对话、首页、资产搜索、Agent 工作台；首页切换概览 / 审批中心。
   除首页外未交付业务显示用户说明与返回首页，不显示特性编号或演示成功数据。
3. 收起 / 展开首页二级菜单，切换后选中态正确；刷新按既定偏好规则恢复，前进 / 后退返回正确地址。
4. 在 1280×720、1440×900 检查布局；仅键盘操作导航、账号、返回及重试，焦点可见。
5. 开发 / 测试构建访问 `/__dev/ui` 检查基础组件和五种状态；生产构建该地址显示不存在。
6. 退出后停留匿名页；显式再次登录必须重新认证（本地输入密码），错误密码不能进入；认证成功后才建立新织境会话。换业务用户验证无权限页且可退出，不循环登录。
7. 在已准入身份下显式访问 `/objects/equipment`，验证旧定义与 10 台设备读取及 trace 链路；它不出现在正式导航。
8. 按自动化夹具复现登录取消 / 无效回调，预期回到 `/auth/error`，只显示安全原因及重新登录 / 返回首页；
   重试生成全新登录请求，不复用原 callback。不能把浏览器在不可达 IdP 站点的网络错误承诺为织境可渲染页面。

## 5. 完整 E2E 与旧链路回归

环境仍在运行且种子数据就绪时执行既有命令：

```bash
make e2e KUBE_CONTEXT=kind-contexture
```

预期：004 外壳浏览器用例及迁移后的旧示例全部通过；旧 demo 改为工程师登录首页后显式访问设备页，
其他网关 / MCP 业务用户权限用例保留。该命令涉及已部署环境，须按原 quickstart 核对，不为验收擅自重建模拟数据。

`make e2e` 包含生产浏览器组与开发组件组；也可独立运行：

```bash
pnpm e2e:browser
pnpm e2e:ui
```

前者使用 `tests/e2e/playwright.config.ts` 与 8080，排除 ui-examples；后者使用
`tests/e2e/playwright.ui.config.ts`，自动启动 5173 的开发服务器，仅运行 ui-examples，真实登录仍在 8080 完成。
这些配置 / 命令已接入；缺环境用例不得静默跳过。完整约定见
[browser-validation.md](contracts/browser-validation.md)，两组结果须分别记录到最终验收文档。

## 6. 提前嵌入验证

按 [embed-readiness.md](contracts/embed-readiness.md) 在隔离临时工作副本内准备锁定上游依赖，
执行其现有 `pnpm --dir web build:embed`，将 ESM / CSS / chunks 导入临时宿主验证，不改产品入口或上游源码。

2026-11-02 已完成隔离安装、官方构建、Vite 宿主与浏览器 / HTTP / WS 验证，Node 22 复核通过，详见 [embed-runtime.md](evidence/embed-runtime.md) 和 [embed-boundaries.md](evidence/embed-boundaries.md)。004 产品 Web 身份已按 US1 独立验证；这里的隔离实测不代表 007 正式 Omnigent 集成。后续复验继续记录：

- 上游提交及宿主共享 React / Router 的实际解析版本；编译命令与结果。
- 路由、深链、刷新 / 返回、CSS / portal、动态资源与 Worker、挂载 / 卸载的实测证据；下游 rspack 适配不能替代 Vite 宿主验证。
- 官方传输注入点和身份信任边界的源码依据；正式服务 / 身份联调仍归 007。
- 缺少环境、失败或需要上游扩展的项目按真实状态记录，不能以“调查已写”替代 SC-007。

本指南完成不自动代表 004 验收通过；自动化结果、兼容性证据与负责人手动验收均需另行记录。

## 7. 交接给 007 的验证

方案 B 的正式 Agent 集成由 007 承担。按 [embed-readiness.md](contracts/embed-readiness.md) 的 007 矩阵，
在其计划与工期定稿前验证：真实身份与会话权限；官方客户端与完整工作台共享同一服务端会话；
OM 资产上下文与来源；切换、重连、去重、取消和退出；会话 MCP 凭证注入与失效；未交付执行能力的服务端拒绝。

这些项目不计入 004 的完成条件，也不在本轮执行。007 的 1.5 周仍为暂估，SDK 依赖、身份接线与同会话实验有结果后复估。

普通 make e2e 不执行 003 重建；专项重建测试仅由 make e2e-mock-data 显式运行。


2026-11-03 主动登录修订已验证。可运行 `pnpm e2e:browser shell-auth.spec.ts` 复验：同一浏览器退出后
再次登录需重新认证，错误密码不能进入，正确认证建立新会话，刷新保持登录。当前本机 BFF 镜像为 004-reauth。


## 8. 用户验收与工程验证的职责（2026-11-03 修订）

用户验收只在 http://localhost:8080/home 的实际产品页面进行。下列事项由开发侧完成并提供证据，
不转交用户手工执行，也不要求用户启动开发服务、输入命令或阅读兼容性报告：

| 工程交付 | 开发侧验证 | 已有证据 |
| --- | --- | --- |
| 基础组件与五类状态（SC-005） | 按钮变体、输入 / 标签、加载结束、重试失败再恢复、无权限和未开放动作 | UI 单元、ui-examples 单元及真实开发浏览器通过，见 evidence/validation.md |
| 新页面接入（SC-006） | 开发示例中的独立内容复用同一 Shell / 页头 / 公共状态，添加演示记录仅更新本地状态 | 接入说明、单元与开发浏览器证据 |
| 嵌入兼容性（SC-007） | 锁定构建、共享依赖、路由 / 样式 / Worker、HTTP / WS 与身份依据 | compatibility.json、embed-*.md；007 的正式联调仍未运行 |
| 旧设备与生产边界（FR-020 等） | 旧设备读取 / 追踪回归，以及生产示例地址不存在 | demo、trace / audit、shell-navigation |

组件演示的人工复核由开发人员执行：先在 8080 登录，同一浏览器打开
http://localhost:5173/__dev/ui，检查按钮 / 输入 / 标签，切换五种状态，结束加载，
勾选和取消“重试仍然失败”并重试，再验证“添加演示记录”。这些步骤不是用户验收要求。

本次仅修订文档职责与操作步骤，不改代码，不重跑或改写既有测试结果；全部工程质量门禁继续保留。


## 9. 登录视觉交付（2026-11-03）

正式入口为 http://localhost:8080/home，Web 镜像 contexture/web:004-login-knowledge；BFF 仍为 004-reauth。
主题按 [安装说明](../../extensions/keycloak/README.md) 交付。修改共享静态源后生成 values 并执行
components-check；外部 Keycloak 重建时需要持久安装主题，不应修改共享 realm 或其他客户端。

开发验证：Web / UI test:coverage、tools/tests/test_keycloak_theme.py、Keycloak test_realm.py，
以及 login-appearance.spec.ts 检查两个尺寸、真实认证、分步提示与密码显隐；整套 make e2e
继续覆盖错误密码、重新认证、本地退出、角色和旧设备链路。用户无需运行上述工程验证。
