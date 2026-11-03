# Implementation Plan: 004 织境 Web 外壳与设计系统

**Branch**: `004-web-shell`（2026-11-03 补建；此前实施分支为 `docs/plan-progress-003`） | **Date**: 2026-11-02（分析问题修订） | **Spec**: [spec.md](spec.md)

**Status**: 已验收通过并关闭（2026-11-03）；[负责人确认](acceptance.md)。历史实施记录保留，最新状态以本行及末尾关闭记录为准。

**Input**: `specs/004-web-shell/spec.md`，含三项澄清：独立退出织境；仅 admin / ai-engineer 准入；2026-11-02 明确不调用 IdP logout。
补充依据：ADR-0002 / ADR-0003 的 2026-11-01 修订，负责人确认方案 B；本次只增量修订计划，不重建 spec 或扩大外壳范围。

## Summary

在现有 Web / BFF 上交付外壳，不新增服务或业务数据库。前端引入共享 UI 包、统一路由与会话状态；
后端复用已有 OIDC、PostgreSQL 会话和身份接口，补 Web 角色门禁、应用内退出及身份服务故障分类。
正式资产搜索、Agent、审批和执行沙箱仍分别归 006 / 007 / 008 / 012。

方案 B 已确定：织境拥有主导航和业务页面，007 在整页嵌入 `OmnigentApp`，页面助手由织境维护，
经 BFF 优先适配官方客户端，与工作台关联同一服务端会话。配置 / 扩展不足时允许依宪法 VI 评估最小补丁，
不复制上游前端。该决定不代表嵌入、身份或同会话交互已经运行通过。

规划采用 React 18.3.1 与 Router 7.18.2 对齐锁定 Omnigent 的共享运行依赖。此为有源码依据的设计选择，
**2026-11-02 已完成隔离实测，T001–T005 门禁通过**。当前证据及局限见 research R14；历史静态依据与 spike 矩阵见
[research.md](research.md) 和 [contracts/embed-readiness.md](contracts/embed-readiness.md)。关键构建验证在实现产品外壳前执行，
失败时先解决依赖 / 构建问题，不能以未验证的嵌入假设推进。

## Technical Context

**Language/Version**: Python 3.12；TypeScript 沿用工作区锁定编译器；Node 22；pnpm 11.20.0。

**Primary Dependencies**:
- Web 从 React / ReactDOM 19.3.1、Router 8.4.0 对齐到 React / ReactDOM 18.3.1、react-router / react-router-dom 7.18.2；
  继续 Vite 8.3.4、Vitest 5.0.5；React 类型包使用 18 系列并在实施时精确锁定、验证编译。
- UI 采用 Tailwind / @tailwindcss/vite 4.3.1、Radix 1.6.3 的必要原语、TanStack Query 5.101.2；版本来自锁定上游的依赖解析，
  宿主兼容尚待 spike。只实现当前基础组件，不引入上游整个应用依赖；不引入 Ant Design、图组件或 Storybook 平台。
- BFF 继续 FastAPI 0.143.3、Authlib 1.9.1、PyJWT、httpx、现有 OTel 与数据库适配；既有依赖精确解析以 `uv.lock` 为准。
- Omnigent v0.18.0，提交 `a8676d23e88df7918f4f8ef1c7c4e3186e710354`，仅作为提前调查 / 隔离试验输入，不进入 004 正式部署。
  官方 Python 客户端 `omnigent-client==0.18.0` 是 007 的优先适配候选，依赖同版 `omnigent`；004 不安装该客户端或增大 BFF 运行依赖。

**Storage**: 继续 BFF 独占的 PostgreSQL 会话库，不迁移表；导航与菜单偏好仅内存，不存令牌、不新增用户偏好服务。

**Testing**: pytest、现有契约测试和真实 Keycloak / PostgreSQL Testcontainers；Vitest / Testing Library；Playwright Chromium。
新增 UI / Web 行覆盖率门槛 ≥80%，需补对应 coverage provider / scripts 与 CI；Python 继续现有覆盖率门槛，另检查变更行。

**Target Platform**: 本地 kind 部署，nginx 静态 Web + Envoy 同源 BFF；桌面 Chromium，1280×720 和 1440×900。

**Project Type**: 既有 monorepo 的前端与 BFF 增量，不新增微服务。

**Performance Goals**: spec 未承诺新的吞吐或延迟 SLO；沿用 SC-001 的 2 分钟身份演练与 SC-008 的 30 分钟人工复验。
静态页面切换不得触发业务服务查询；业务接口延迟、并发容量不作为 004 新增目标。

**Constraints**: HTML 原型只作输入；亮色 / 简体中文；企业认证后服务端角色门禁；本地会话退出不调用 IdP 全局退出；
未经验证的用户头不可作为上游身份；不能把产品能力占位或技术调查当成真实业务演示。

**Scale/Scope**: 4 个一级入口、首页 2 个二级入口、1 个受保护旧设备演示入口、5 类公共状态、1 个开发组件示例；
无资产采集 / 搜索 / Agent 会话 / 审批处理 / 沙箱服务新增。

## Constitution Check

以下是设计符合性检查，不代表测试或手动验收已通过。前置检查基于明确范围，设计后根据本目录契约复核。

| 条款 | 前置检查 | 设计后复核 / 验证安排 |
| --- | --- | --- |
| I TDD / ≥80% | 计划先契约与失败测试再实现 | 角色、故障、退出先写失败用例；真实 IdP / 会话库集成，前后端覆盖率与浏览器验证后交付 acceptance |
| II 边界与契约 | 仅修改 Web、BFF 与公共包 | 无共享数据库越界；接口行为先更新契约；角色收紧与退出策略须按下文迁移方案处理兼容性 |
| III 开源与许可 | 复用许可允许的库和现有服务 | 依赖清单见下表；新依赖冻结锁文件；Web 同样纳入 SBOM / 许可 / 漏洞检查，不默认 CI 已覆盖 |
| IV 身份 / 最小权限 | 单租户，Web 仅 admin / ai-engineer | Cookie 和 Bearer 都检查角色；401 / 403 / 上游故障区分；拒绝用户仍可退出；不改变 MCP 消费者权限 |
| V 可观测 | 复用 BFF OTel、统一错误格式 | 拒绝与身份依赖故障保留 trace_id / tenant_id，不记录令牌；不新增具体厂商 SDK |
| VI 第三方集成 | 配置 / 官方入口优先，方案 B 已确认 | 004 不复制或修改上游源码；007 / 012 必要扩展与最小补丁按上游优先和登记规则处理，不以浏览器身份头或 CSS 绕过边界 |
| UI 先行 | 当前 HTML 与 spec 文字定义分期范围 | 原型不作为实现代码；004 只验收外壳；修改界面需求需同步 spec |
| 交付 / 治理 | 不在本轮实现或合并 | tasks 最后阶段必须安排自动验证后编写 acceptance；负责人手动验收，PR 非 squash，CI 全绿 |

### 开源服务与主要库清单

| 组件 | 版本 / 依据 | 许可 | 用途 / 部署位置 | 可替换方案 |
| --- | --- | --- | --- | --- |
| Keycloak | 26.8.0；现有外部实例，客户接入约束沿用 001 | Apache-2.0 | 企业认证，现有身份服务 | 兼容 OIDC 的 IdP（需另评估） |
| PostgreSQL | 17.6 | PostgreSQL License | BFF 独占会话 database | 其他会话存储需另作 ADR |
| FastAPI / Authlib | 0.143.3 / 1.9.1 | MIT / BSD-3-Clause | BFF HTTP / OIDC | 不在 004 更换 |
| React / ReactDOM | 18.3.1 | MIT | Web 及未来嵌入共享运行时 | 保持 19 须重新验证上游兼容，不默认双实例隔离 |
| React Router | 7.18.2 | MIT | Web 路由及未来嵌入共享上下文 | 其他路由需上游适配，不采用 |
| Vite / Vitest | 8.3.4 / 5.0.5 | MIT | 构建 / 测试工具，不进运行服务 | 沿用现有工具链 |
| Tailwind / Radix / TanStack Query | 4.3.1 / 1.6.3 / 5.101.2 | MIT | Web 样式、交互原语、身份请求缓存 | 原生组件可用于简单控件，不引入整套其他 UI 框架 |
| nginx | 1.31.7，组件清单为准 | BSD-2-Clause | 静态 Web 镜像 | 兼容静态服务器 |
| Omnigent | v0.18.0 / 上述提交 | Apache-2.0 | 仅提前试验；007 才正式部署 | 暂不替换运行时 |

新依赖的许可证与传递依赖以实施后 SBOM 再核验，本表不是扫描结果。现有 OM 只参与旧示例回归，不复制其 UI。

## Project Structure

### Documentation (this feature)

```text
specs/004-web-shell/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── contracts/
│   ├── web-shell.md
│   ├── bff-session.md
│   ├── browser-validation.md
│   └── embed-readiness.md
├── checklists/
│   ├── requirements.md
│   └── security-license.md
└── prototype/index.html
```

`tasks.md` 已于 2026-11-02 开始实施，T001–T005 已完成；`acceptance.md` 在实现和自动化验证后生成，不提前伪填验证结果。

### Source Code (repository root)

以下是拟改动位置，本轮未创建这些产品代码。

```text
apps/web/src/
├── App.tsx / main.tsx / api.ts
├── auth/             # 身份状态、Web 准入、重试 / 退出
├── layout/           # AppShell、一级 / 二级导航、页头与账号
├── pages/            # Home、未开放页、不存在页、原 ObjectsPage
├── i18n/zh-CN.ts
└── __tests__/
packages/ui/          # 新共享包 @contexture/ui：原生基础控件 + 必要 Radix 原语、tokens、状态示例与组件测试
packages/ts-api/       # 继续由根 OpenAPI 生成；不手改声明文件
services/bff/src/contexture_bff/api/
├── deps.py           # require_web_context：鉴权之后检查角色
├── me.py / objects.py
└── auth.py           # 应用内会话退出
packages/py-core/src/contexture_core/auth.py  # JWKS 故障分类，不加入 Web 专属角色规则
services/bff/tests/   # 单元、契约、真实依赖集成
contracts/openapi/bff.yaml
apps/web/README.md / tests/e2e/ / .github/workflows/ci.yml
```

**Structure Decision**: UI 包按 ADR-0003 放在 monorepo 独立前端包中，不另建演示服务。
开发示例走仅开发 / 测试构建启用的 `/__dev/ui`，生产返回不存在；用原生示例页，不新增 Storybook 工程。
001 的 `/objects/:typeKey` 保留受保护的回归入口，不进入菜单；登录后的根路径转到首页。

## Design Decisions

1. **会话状态机**：`checking → authenticated | anonymous | forbidden | unavailable`；失败不统一降成未登录。
   TanStack Query 只缓存 Me，关闭身份的无限重试，401 / 403 不重试；切换页面不重复创建会话。
   文档刷新重新检查，窗口重新聚焦 / 到期后再请求时重新验证；后端对每次受保护调用执行门禁。
2. **后端门禁**：在 BFF 专属依赖中检查 `admin OR ai-engineer`，同时保护 `/me` 与现有两类 object 路径；
   不修改通用 Authenticator 的业务用户准入，不将 Web 角色限制扩散到网关 / MCP。callback 允许建立无 Web 权限的会话，
   随后 `/me` 返回 403；拒绝页允许退出，不循环跳认证。health / login / callback / logout 不加 Web 角色门禁。
3. **退出**：删除本地会话并过期 Cookie；不调用 Keycloak logout、Paperclip 或其他客户端。204 后停留匿名页，
   不立即重新发起 SSO；再次点击登录统一要求重新认证：Keycloak 授权地址固定 prompt=login，认证成功后才建立新的织境会话。失败保留错误与重试，不假报退出成功。
4. **错误分类**：缺少 / 无效身份为 401，受众不匹配保留已有 403，缺 Web 角色为 403 `auth.web_access_denied`；
   身份网络 / 5xx / JWKS 暂时故障为 502 `upstream.unavailable`，保留仍有效的会话记录但不使用过期令牌；
   确定 invalid_grant 才结束会话；会话库和未预期异常返回统一 500，不泄露敏感细节。
   以上为 JSON API 与内部错误分类；浏览器 login / callback 的失败按第 10 项映射为固定目标的 303，不让用户停留在 JSON 文档。
5. **路由与占位**：见 UI 契约。顶栏搜索与“问 Agent”在 004 **隐藏**，避免未开放控件占用键盘焦点；
   四个一级入口保留可访问解释页。首页保留布局，缺数据显示“尚未接入 / 尚未开放”，不加载 OM / Agent。
6. **兼容性研究**：源码证明官方 build:embed 使用 Vite，CSS 有作用域，宿主提供 Router；
   产物是 ESM / chunks / CSS 的中间构建，现有下游适配面向 rspack，不能据此认为 Vite 宿主已兼容。
   004 在产品依赖调整前验证共享运行依赖、路由、动态资源、Worker 和样式范围，不拿静态证据代替。
7. **007 的身份风险**：上游浏览器会产生 X-Forwarded-Email，不能转发为授权依据；
   其 OIDC / accounts Bearer 路径验证自身 HS256 会话令牌。`AuthProvider` 注入是候选扩展接缝，启动接线与
   Keycloak 签名身份桥接仍需 007 实测，不假设“注入 Bearer 即可识别用户”。
   `sidebarConfig` 不是终端 / 执行开关，007 必须有服务端能力拒绝，004 不提供这些执行功能。
8. **工作台与助手分工**：007 整页工作台采用官方嵌入，轻量助手采用织境组件，经 BFF 复用官方 SDK / API；
   两者延续同一服务端会话。嵌入没有现成页面上下文或业务卡片渲染参数，不能默认挂两份工作台即可实现共享。
   四类结果组件先服务助手与业务页面；嵌入内专用渲染输出可行性结论，不扩大 004 范围。
9. **定制边界**：品牌走服务端 branding，明暗 / 路由 / 传输走对应嵌入接口；先保留工作台默认样式。
   浏览器插件 V1 是无网络访问的隔离页面与有限 SDK，不能作为直接请求 BFF 的通用业务页面容器。
   中文化、导航裁剪与深度视觉统一需逐项核查，不能当作现有配置已支持。
10. **登录失败恢复**：既有 callback 接受成功 code + state 或拒绝 error + state，先验证并一次性消费 state，
    成功才换码。BFF 可处理的取消 / 拒绝 / 暂时故障 / 内部失败返回 303 到公共 `/auth/error`；只携带允许的原因码、
    安全 trace_id 与经过校验的站内目标，不传 code / state / token / 上游错误原文。该页在会话门禁之前匹配，复用 PageState，
    不展示账号或业务内容；重新登录生成新请求，返回首页正常鉴权，不自动重放 callback / SSO。
    细则见 [bff-session.md](contracts/bff-session.md#登录导航失败与恢复)；IdP 页面或服务整体不可达时不承诺接管浏览器网络错误。
11. **线上 Me 与 UI 模型**：Me 的 display_name 为可缺省 string、roles 可缺省；CurrentUser 在 UI 边界归一为
    display_name: string / null 与 roles: string[]。2026-11-02 负责人确认姓名 → 用户名 → user_id 回退，保留 v1 字符串契约并重新生成类型，字段集合不变；
    不将这次契约校正视为角色 / 退出 / 登录导航行为已经迁移。

### 两个验证节点与后续交接

| 节点 | 工作与证据 | 影响 |
| --- | --- | --- |
| 004 产品依赖调整之前 | 锁定上游 build:embed + 临时 Vite 宿主真实构建 / 挂载；共享 React / Router、深链、刷新、卸载、CSS / portal、chunks / Worker；记录版本、命令和结果。代理 / 身份方案保留源码依据，待真实联调项逐项交给 007 | 通过后再调整产品依赖；失败先形成解决路径。004 不引入正式 Agent 服务或产品代理 |
| 007 计划与工期定稿之前 | 隔离验证真实身份与会话权限、OM 上下文、官方 SDK 与工作台同会话延续、断线恢复 / 去重 / 取消、退出，以及执行能力服务端拒绝；评估 SDK 依赖和 MCP 凭证生命周期 | 属于 007 的验证与实现范围；当前 1.5 周是暂估，按结果复估并更新受影响排期 |

007 须区分“Omnigent 识别用户”与“Agent 持委托令牌访问下游”。会话 MCP headers 会写入 Agent 包，
不能以静态 Authorization 配置代替动态凭证管理；007 明确有效期与失效处理，012 完成续期 / 执行恢复加固。
完整矩阵见 [embed-readiness.md](contracts/embed-readiness.md)；这些后续事项不增加 004 的用户故事或验收项。

## Validation & Migration

- 先更新根 OpenAPI 的行为说明 / 显式响应，再写门禁、退出和错误分类的失败测试；Me / ErrorEnvelope 字段集合保持。
  display_name 保持 v1 string；T014 补字符串 / 缺省通过、null / 非法类型拒绝及 BFF 身份回退的回归，不用强制类型断言回避差异。
- 角色收紧及退出变更是**有意的行为迁移**：001 的 business-user Web 成功样例改为 engineer1 / admin1；
  通用 JWT 夹具的 business-user 默认值不整体替换，网关 / MCP 的业务用户测试保留。
- 依据宪法 II，在实施前由契约评审核定该安全策略收紧是否构成需新版本的破坏性变更。
  本设计采用现有 v1 的安全策略修正，前提是该 BFF 尚无需保持旧业务用户准入的外部消费者；
  该前提须在契约评审中验证，如不成立必须版本化迁移而不能绕过 oasdiff 或修改宪法。
  同时核对 login / callback 失败改为 303 对现有直接调用方的影响，不仅核对 Me 的字段集合。
- Python：角色矩阵含五组与直接 Bearer 绕过；invalid_grant 与网络故障分开；JWKS 故障不注销；
  删除会话 / Cookie、无会话幂等退出、退出无 IdP 副作用；真实 Keycloak + PostgreSQL 验证各边界。
- Web：导航、首页与四个入口、收起恢复、403 无登录循环、502 重试、退出失败、中文长文案、键盘与两个桌面尺寸。
- 旧 demo：engineer1 登录到首页，再显式访问 `/objects/equipment` 验证真实 OM / Doris 与追踪，保留 001 骨架回归。
- CI：增加 packages/ui 的测试与 Web / UI coverage 门禁；Web 与 BFF 均纳入 SBOM / 许可扫描；保留现有 API 生成检查、oasdiff、
  补丁检查和真实集成测试。`make e2e` 执行前确认本地平台与种子数据，不能以纯前端 mock 替代身份验收。
- 浏览器验证分为生产组 8080 与开发组件组 5173：前者排除 ui-examples 并断言生产示例不可用，后者只执行示例用例；
  开发组先在同一 BrowserContext 通过 8080 已注册回调真实登录，再访问 5173，复用同主机 Cookie 与 BFF 代理。
  不增加 IdP 回调、不改共享 realm，具体配置、命令和证据见 [browser-validation.md](contracts/browser-validation.md)。
- 按开发计划复核 [安全 / 许可需求清单](checklists/security-license.md)，该清单是需求质量评审记录，不是实施测试通过记录；
  生成项保持未勾选，评审结果由评审者填写。
- 新页面接口只要发生变化，契约先行；最终实现采用已确认的 v1 字符串回退；依赖、CI 与外壳现已实施，详见最终验证记录。

## Phase 0 / Phase 1 Status

- Phase 0：静态代码研究与设计取舍已写入 research；身份与退出规则已通过三项澄清明确。
- Phase 1：状态模型、UI / BFF / 嵌入调查契约与 quickstart 已生成。
- 2026-11-01：已将方案 B 同步到本计划、research 与嵌入验证契约；004 spec / 原型保持原有范围，007 事项只作交接。
- **前置门禁已通过（2026-11-02）**：官方嵌入构建、Vite 8.3.4 宿主与浏览器挂载、共享依赖 / 路由 / 样式 / Worker、HTTP / WS 隔离试验均已记录。Node 22.20.0 复核通过；不修改上游、不开产品代理。见 [research R14](research.md#r14-2026-11-02-实测与当前宿主选择t001t005) 与 [结构化证据](evidence/compatibility.json)。允许进入 T006 / T007；004 产品验收和 007 正式集成尚未通过。
- 2026-11-02：已生成 [tasks.md](tasks.md)，共 48 项，按兼容性前置验证、公共基础、US1、US2 与最终验收组织；下一步做 spec / plan / tasks 一致性检查。
- 2026-11-02 分析修订：已对齐 Me 可空契约，补齐登录失败恢复、004 / 007 身份验证分工、双环境浏览器验证和安全 / 许可需求清单；
  负责人随后明确不调用 IdP logout，已同步 spec 的澄清、FR-004 与边界情况，I1 文档冲突已关闭。
  清单尚待评审，实际身份 / 浏览器验证仍未执行；退出运行逻辑按 T016 / T018 → T024 测试先行实施。
- 以上为规划阶段历史状态；2026-11-02 的当前实现和验证状态以文末及 evidence/validation.md 为准。

## Complexity Tracking

未申请宪法例外。身份头缺口、构建实测与契约行为迁移属于显式门禁，不使用理由表豁免。

### 2026-11-02 实施状态补充

负责人确认“确定没有问题，开工吧”，允许在清单标记保持原状时继续。T001–T005 已完成，采用 React 18.3.1 / Router 7.18.2 / Vite 8.3.4 的宿主组合；真实身份桥接与工作台会话按原分工交接 007。现有产品依赖尚未调整，下一阶段先迁移根契约，再创建 UI 包与测试基础。以上补充取代早期“未执行 spike”的当前状态表述，历史研究按日期保留。

### T006 兼容决定（已确认）

实际 oasdiff 对 v1 Me.display_name nullable 校正报 response-property-became-nullable。参数长度描述已校正，仅余这一项失败。历史停点：T006 当时未完成，T007 未开始；推荐保留 v1 字符串契约，先测试再修复 BFF 在姓名 / 用户名均缺失时的 user_id 回退。可评审方案与备选版本化迁移见 [contract-migration.md](evidence/contract-migration.md)，负责人已回复“可以”，采用保留字符串保证及后端回退方案；继续执行，不豁免门禁。


### T045 实际宿主复核（2026-11-02）

React / React DOM 18.3.1、Router / Router DOM 7.18.2、Vite 8.3.4、pnpm 11.20.0 与 T001–T005
隔离证据一致，Docker Node 22.23.4 / npm 12.2.1 的生产构建及扫描复核见最终验证记录（原 Node 22.23.2 已被扫描阻断并替换）；未改变官方嵌入方案或上游源码。
四主题的实测 / 静态依据及 007 not_run 边界保持，不能把 004 的真实 Web 登录推定为 Omnigent 身份桥接通过。

T001–T040 已落实，最终覆盖率、扫描及端到端结果见 [validation.md](evidence/validation.md)。
当前不是负责人验收完成状态；T047 / T048 必须等待实际手动验收。


### 本机交付与验收入口（2026-11-02）

T001–T046 实现与本机自动验证已落实：Python 279、Web 54、UI 18 用例通过；
端到端 12 集群 / 10 生产浏览器 / 1 开发浏览器通过，覆盖率与 Critical 扫描门禁通过。
见 [最终验证](evidence/validation.md) 与 [负责人验收](acceptance.md)。
当前待 T047 负责人手动验收，T048 不更新为完成；后续顺序与 007 暂估 / 未验证边界保持。
PR 提交组织、远端 CI、评审与合并不在本次自动执行范围。


### 2026-11-03 主动登录重新认证修订（负责人已确认）

首次登录、退出后登录与失败页重新登录共用 BFF /login；KeycloakOidc 固定加入 prompt=login，
保留 PKCE、state、nonce、站内目标与现有错误分类。正常 /me 检查及 refresh 不经过授权入口。
不增加前端退出标记，不开放 prompt 覆盖参数，不改变退出接口或企业 SSO / 其他客户端会话。
先修改契约、编写真实适配器与带 SSO Cookie 的失败测试，再实现并真实浏览器验证；见 T049–T052。
旧自动验证为历史记录；本次结果另按日期追加，负责人手动验收仍待执行。


2026-11-03 修订结果：T049–T052 完成，135 项鉴权回归、13 项真实身份集成、全量 284 项测试及
12 集群 / 11 生产浏览器 / 1 开发浏览器全部通过。本机 BFF 已更新为 004-reauth，覆盖率与受影响镜像扫描门禁通过。
详见 evidence/validation.md 的当日修订记录。T047 / T048 仍待负责人手动验收，不预填通过。


### 2026-11-03 用户验收职责修正

acceptance.md 只保留用户在 8080 正式页面执行的操作；开发组件页、按钮变体、故障模拟、独立接入演示、
旧设备回归和兼容性报告由开发侧执行并交付证据，操作说明放入 quickstart.md。
SC-005 / SC-006 / SC-007 和 FR-020 等工程交付保持，不向用户转交工程操作，不以减少用户步骤删除测试或降低门禁。
本次仅修订文档，不改变应用或既有实测结果，T047 / T048 仍待用户实际确认。


### 2026-11-03 登录外观实施（提案 B 已确认）

复用 apps/web 与 packages/ui，新增共享身份页布局 / 静态视觉资源；Keycloak 走官方父主题继承、CSS 和渐进增强布局扩展。
不新增服务或依赖，不复制原型代码，不覆盖官方密码表单 / 授权流程。共享资源从 packages/ui/identity 构建进主题；
extensions/keycloak 只维护官方扩展，主题由 ConfigMap 挂载到自带 Keycloak，外部身份服务安装同一资源包。
只给 contexture-bff 客户端设置 login_theme=contexture；不改 realm 默认主题及其他客户端。
新增静态主题打包 / 一致性工具，生成的 Helm values 随部署 / 离线包交付，无需离线执行构建工具。
Constitution Check：原型已确认；接口字段与认证契约不变；官方扩展优先；测试先行；真实身份回归和差异覆盖率保留；用户验收只看正式页面。


实施结果：T053–T057 完成，正式入口与企业认证视觉已部署到本机；290 Python、58 Web、24 UI、
26 端到端验证通过。主题仅作用于织境客户端；共享 realm 及其他 10 客户端完整配置保持。
外部容器重建后的主题持久化、原有许可人工复核和缓存漏洞库日期如实记录于 evidence/validation.md。
T047 / T048 保持待产品负责人实际验收。


### 2026-11-03 验收关闭

产品负责人明确确认“spec04验证完了，可以关闭了”。T047 验收通过，T048 状态同步完成，
004 按既定外壳范围关闭；登录视觉及后续文案修订包括在本次确认中。
[验收记录](acceptance.md) 与 [工程证据](evidence/validation.md) 保留实际结果和限制。
后续顺序继续为 005 → 006 → 007 → 008；007 暂估与真实身份 / 上下文 / 同会话待验证项保持。
本次不重跑测试、不创建提交 / PR、不执行合并或部署；远端 CI 和独立评审未据此声称通过。
