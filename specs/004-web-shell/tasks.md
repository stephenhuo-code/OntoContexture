# Tasks: 004 织境 Web 外壳与设计系统

**Input**: `specs/004-web-shell/` 的 spec、plan、research、data-model、contracts 与 quickstart；宪法 v2.0.0；ADR-0002 / ADR-0003 的 2026-11-01 方案 B 修订。

**Created**: 2026-11-02

**Status**: 已验收通过并关闭（2026-11-03）。T001–T060 已完成，产品负责人确认见 [acceptance.md](acceptance.md)。未自动提交或合并。

**实施进展（2026-11-02）**: T001–T005 完成；T006 已按负责人确认恢复 v1 字符串保证、补测试并修复 BFF 显示名称，oasdiff 通过；T007–T012 公共基础及 T013–T029 US1 已通过独立验证；开始 US2 导航与布局。

**2026-11-02 修订**: 已按分析修复 I2 / U1 / A1 / U2 / G1；Me nullable 根契约与生成类型已校正，登录失败恢复及双环境测试为待实施设计，新增安全 / 许可清单待评审。负责人已明确不调用 IdP logout，I1 文档冲突已关闭；实际退出变更仍由 T016 / T018 → T024 实施，任务编号和范围保持。

**Tests**: 依宪法 I、spec Assumptions 和 plan，生产实现必须遵循红 → 绿 → 重构，测试先于对应实现提交，保留非 squash 历史。单测允许替身；身份与会话集成使用真实 Keycloak / PostgreSQL，旧设备 E2E 使用真实 OM / Doris / 网关链路。

**Organization**: 仅 US1、US2 两个用户故事，均为 P1；按身份基础 → 导航布局推进。D1 设计系统、D2 工程验证属于公共交付，不新建用户故事。

## Format: `[ID] [P?] [Story] Description`

- 所有任务使用 `- [ ] Txxx`；`[US1]` / `[US2]` 只出现在对应故事阶段。
- `[P]` 表示所属并行批次的共同前置条件满足后，可在不同文件中独立工作；不表示可以越过阶段门禁。
- 路径均相对仓库根目录；当前不存在的文件是拟新增文件。`evidence/` 是本特性的验证附件目录，不是新服务。
- 本轮只生成任务；实现时每轮先运行对应测试，确认因预期行为缺失而失败，再提交测试、实现和重构。不得把依赖安装失败或语法错误当作有效红测。
- 环境不足、失败与未执行均按实际记录，不勾选受阻任务、不宣称通过；未经负责人验收，不把 004 标记完成。

## Phase 1: Setup — 基线与嵌入兼容性前置验证

**Purpose**: 在调整产品依赖前验证方案 B 的宿主技术选择；不部署正式 Omnigent 服务。

- [X] T001 核对 004 范围、原型 SHA-256、宿主工具版本、现有测试基线及上游锁定提交，在 `specs/004-web-shell/evidence/baseline.md` 记录命令、结果与环境限制；读取 `specs/004-web-shell/checklists/security-license.md` 的需求评审记录，未确认项保持待评审；以 `specs/004-web-shell/spec.md` 2026-11-02 澄清为退出基线：只结束当前织境会话，不调用 IdP logout，不把决策确认当作运行实现已完成。
- [X] T002 在隔离临时目录准备 `third_party/omnigent/src/` 锁定提交 `a8676d23e88df7918f4f8ef1c7c4e3186e710354` 的工作副本，按上游锁文件安装并执行 `pnpm --dir web build:embed`，将实际版本、退出码及 ESM / CSS / chunks / Worker 产物记录到 `specs/004-web-shell/evidence/embed-build.md`；保存可重建临时宿主的最小配置与命令，不修改子仓库、不将上游完整源码或 node_modules 纳入主仓库。
- [X] T003 使用 T002 产物，在临时 Vite 8.3.4 宿主以 React / ReactDOM 18.3.1、react-router / react-router-dom 7.18.2 实测构建与浏览器挂载，验证仅一份 React / Router、深链、刷新、前进 / 后退、卸载、CSS / portal、动态资源与 Worker、离线静态资源加载；将配置、复现命令、控制台 / 网络证据和逐项结果写入 `specs/004-web-shell/evidence/embed-runtime.md`，不以类型检查代替运行验证。
- [X] T004 在隔离实验验证官方 fetcher / resolveWebSocketUrl 的注入、路径改写、取消与连接生命周期接缝，将代理路径、WS 握手及会话失效设计依据写入 `specs/004-web-shell/evidence/embed-boundaries.md`；核对锁定源码的 `/v1/me`、自身 HS256 会话、AuthProvider / create_app 接线及浏览器身份头风险，依据 `specs/004-web-shell/contracts/embed-readiness.md` 列出 007 的真实身份、SDK 同会话、MCP 凭证与服务端执行拒绝交接项，不实现产品代理或签名身份桥接。
- [X] T005 将 T002–T004 证据汇总到 `specs/004-web-shell/research.md` 并在 `specs/004-web-shell/plan.md` 记录宿主选择与阻塞处理；每个主题记录 upstreamCommit、hostDependencyVersions、topic、procedure、result、evidenceLocation、limitations、ownerFeature，遵守模型原文“result = static_confirmed / runtime_pass / runtime_fail / not_run；not_run 不能折算为通过。”；影响当前宿主的失败先形成处理决定并复测，关键实测未完成时不得进入 T007，007 真实集成的未验证项单列。

**Checkpoint**: 构建与运行有真实证据，代理和身份有可验证的设计依据，影响 004 选型的阻塞已经处理；架构决定与运行通过记录明确区分。

## Phase 2: Foundational — 契约、共享 UI 与构建基础

**Purpose**: 两个故事共用的工程基础。依赖 Phase 1；本阶段不新增业务 API、数据库实体或迁移。

- [X] T006 在 `specs/004-web-shell/contracts/bff-session.md` 记录 BFF 消费者核对与行为兼容评审，覆盖角色收紧、退出和登录导航失败改为 303；若存在需兼容的外部消费者，先补版本化迁移方案，不绕过 oasdiff。更新 `contracts/openapi/bff.yaml` 的角色、退出、JSON API 错误和 login / callback 的 303、Location、安全响应头及 code / error 与 state 条件约定；按负责人确认保留 Me.display_name 可缺省 string，BFF 姓名 → 用户名 → user_id 回退，字段集合不变；按契约重新生成 `packages/ts-api/src/bff.d.ts`，不手改生成类型。
- [X] T007 在 T005 通过后更新 `pnpm-workspace.yaml`、`apps/web/package.json`、`pnpm-lock.yaml`，创建 `packages/ui/package.json`、`packages/ui/tsconfig.json`、`packages/ui/vite.config.ts` 与 `packages/ui/src/test-setup.ts`；对齐已验证的 React / Router，精确锁定 React 18 类型、Tailwind 4.3.1、必要 Radix 1.6.3、Query 5.101.2、匹配 Vitest 的 coverage provider，配置 Web / UI test、build、test:coverage 及报告输出；UI 使用 React peer dependency，不引入整套上游依赖、Storybook 或 Omnigent Python SDK。
- [X] T008 [P] 在 `packages/ui/src/__tests__/primitives.test.tsx` 先写 Button、TextInput、Panel、StatusBadge、Tooltip 的行为测试，覆盖主 / 次、disabled、busy 防重复操作、输入标签、键盘、可见焦点、悬停与聚焦提示、长中文及文字状态说明；确认新组件缺失时失败。
- [X] T009 [P] 在 `packages/ui/src/__tests__/page-state.test.tsx` 先写状态行为测试，采用模型原文“kind = loading / empty / error / forbidden / not_open / not_found；”及“title、description、actionLabel、action、busy、traceId（仅安全诊断字段）。”，覆盖加载结束、重试成功 / 再失败、无权限不重试获权、未开放 / 不存在返回首页、空内容下一步与安全诊断，不混用空内容和未开放。
- [X] T010 在 T008 红测之后实现 `packages/ui/src/tokens.css`、`packages/ui/src/components/Button.tsx`、`packages/ui/src/components/TextInput.tsx`、`packages/ui/src/components/Panel.tsx`、`packages/ui/src/components/StatusBadge.tsx`、`packages/ui/src/components/Tooltip.tsx` 与 `packages/ui/src/index.ts`，提炼亮色语义 tokens、必要交互原语、中文本地字体栈与可访问样式；让原语测试通过，不复制 HTML 原型或上游组件代码。
- [X] T011 在 T009 红测及 T010 完成后实现 `packages/ui/src/components/PageState.tsx` 并导出，落实模型原文：`error 可重试；forbidden 可返回 / 退出而不能“重试获权”；not_open 只有说明与首页入口。`；组件接受文案与动作参数、不包含业务服务或角色逻辑，满足全部状态测试。
- [X] T012 在 `apps/web/vite.config.ts`、`apps/web/src/styles.css`、`apps/web/src/main.tsx` 接入共享样式与构建插件，更新 `apps/web/Dockerfile` 将 `packages/ui/` 纳入冻结锁文件构建；运行现有 Web 回归、UI 测试与 Web / UI 构建，证明本地及 nginx 镜像均可消费共享包，结果记录到 `specs/004-web-shell/evidence/foundation-validation.md`。

**Checkpoint**: 契约先行、依赖已验证、UI 组件有行为测试且镜像可构建；US1 可以开始。此时尚无新外壳交付。

## Phase 3: User Story 1 — 登录织境、进入首页并查看当前账号 (Priority: P1) 🎯 MVP

**Goal**: 复用真实企业身份，实施 Web 服务端准入、真实账号、故障分类和独立退出；先提供可使用的首页身份入口。

**Independent Test**: 无需搜索、Agent 或审批服务；在真实 Keycloak / PostgreSQL 环境完成登录 → 真实首页账号 → 退出 → 刷新 / 后退 / 旧 Cookie 拒绝 → 显式重新登录。五组角色通过 Cookie 和 Bearer 验证；403 不循环登录、502 可重试。正常身份演练满足 SC-001 的 2 分钟要求。

### Tests for User Story 1 — 先失败，再实现

- [X] T013 [US1] 在 `services/bff/tests/bff_fakes.py` 为 Web 用例提供显式角色参数，调整 `services/bff/tests/unit/test_auth_api.py`、`services/bff/tests/unit/test_objects.py`、`services/bff/tests/contract/test_contract.py` 的成功夹具为准入角色；保留 business-only / 空角色拒绝输入，不整体替换 `tests/support/jwt.py` 的业务用户默认值，不改 MCP / 网关成功身份约定。
- [X] T014 [P] [US1] 在 `services/bff/tests/contract/test_session_contract.py` 先写 login / callback / logout / me / 两类 object 路径的行为契约用例，区分浏览器登录失败的 303 与 JSON API 的 401 / 403 / 502 / 500；覆盖 Location 固定同源、no-store / no-referrer、条件参数、Cookie / Bearer、受众错误、局部退出 204 和无敏感正文；补 Me.display_name 字符串 / 缺省通过、null / 非法类型拒绝的 Schema 用例和 BFF 缺少姓名 / 账号声明的响应回归。保留 `services/bff/tests/contract/test_contract.py` 的生成式覆盖；既有行为作为绿色回归，新增行为记录预期红测。
- [X] T015 [P] [US1] 在 `services/bff/tests/unit/test_web_access.py` 先写五组角色矩阵（admin、ai-engineer、business-only、无准入角色、多角色），覆盖直接 Cookie / Bearer 请求 `/me` 及两类 object 路径、伪造用户 / 角色头无效、拒绝后不访问下游；验证 health / login / callback / logout 不套 Web 角色门禁，缺角色用户可建立身份会话后被 Me 拒绝并安全退出。
- [X] T016 [P] [US1] 在 `services/bff/tests/unit/test_auth_api.py` 先补 safe return_to（查询、站外、双斜线、反斜杠）、成功 code + state、取消 error + state、两者同时 / 均缺失、无效 / 过期 / 重放 state 的测试；断言 state 先校验且一次性消费，拒绝形式不换码，失败 303 仅携带白名单参数，无效 state 回退 /home、不重放 code；按 `specs/004-web-shell/contracts/bff-session.md` 区分明确 invalid_grant、网络 / IdP 5xx、会话库 / 未预期异常，保留刷新寿命、临时故障保留记录而禁用过期令牌、本地删除失败不返回 204、幂等退出与无 IdP logout 副作用用例，替换旧的“所有刷新失败都是 401”断言。
- [X] T017 [P] [US1] 在 `packages/py-core/tests/test_auth.py` 先补 JWKS 网络 / 5xx 与无效签名的区分、缺失 / 空主体拒绝、部署 tenant_id 不受用户头覆盖的测试；保留 wrong audience 403 与通用 Authenticator 接受合法 business-user 的回归，证明库级变更不引入 Web 专属角色限制。
- [X] T018 [P] [US1] 在 `services/bff/tests/integration/test_auth_flow.py` 复用真实 Keycloak / PostgreSQL Testcontainers，准备仅测试 realm 的五组身份并验证登录、角色拒绝、Cookie 安全属性、服务重启后会话、刷新寿命、本地退出及旧 Cookie 失效；以真实刷新撤销、依赖停用 / 网络故障注入验证 401 / 502 / 500 与记录保留 / 恢复，不以 FakeOidc / FakeSessions 替代被集成系统、不改共享 realm 或 Paperclip。
- [X] T019 [P] [US1] 在 `apps/web/src/__tests__/api.test.ts`、`apps/web/src/__tests__/session.test.tsx` 先写身份状态与请求测试，按模型原文进入条件覆盖 checking“初次访问、显式重试、需要重新核对身份”、authenticated(user)“Me 200 且服务端已准入”、anonymous“Me 401 或 logout 204”、forbidden“Me 403”、unavailable(error)“网络 / 502 / 500”；覆盖旧用户清理、重试恢复、焦点 / 页面恢复、迟到响应、显示名 null / 缺省 / 空 / 长文本、roles 缺省归一、退出失败 / 幂等重试及不自动 SSO；补公共 `/auth/error` 在 Me 不可用时可见、reason / trace_id / return_to 白名单、无敏感参数显示、重新登录新建请求且不重放 callback 的测试。
- [X] T020 [P] [US1] 在 `tests/e2e/shell-auth.spec.ts` 和 `tests/e2e/helpers/login.ts` 先写真实登录、账号、拒绝 / 退出、匿名直达、刷新 / 后退、取消 / 无效回调经 303 回到 `/auth/error`、安全诊断及全新登录恢复用例；按 `specs/004-web-shell/contracts/browser-validation.md` 为后续开发组提供在同一 BrowserContext 先通过 8080 登录的 helper，不导出 Cookie / 令牌。把 `tests/e2e/demo.spec.ts` 与 `tests/e2e/test_trace_and_audit.py` 的 Web 成功路径迁为 engineer1 / admin1 登录首页后显式访问 `/objects/equipment`，保留真实定义、10 台设备及 HttpOnly Cookie 断言，不改历史 001 验收文档。

### Implementation for User Story 1

- [X] T021 [US1] 在 T017 红测后修改 `packages/py-core/src/contexture_core/auth.py`，将暂时 JWKS HTTP 故障归为现有 `UpstreamUnavailable`，保留无效令牌 401 与受众错误 403，拒绝缺失 / 空主体；复用 `packages/py-core/src/contexture_core/errors.py` 的安全错误与 trace_id，不增加 Web 角色规则、不记录令牌。
- [X] T022 [US1] 在 T014 / T015 红测后于 `services/bff/src/contexture_bff/api/deps.py` 添加 require_web_context，并接入 `services/bff/src/contexture_bff/api/me.py`、`services/bff/src/contexture_bff/api/objects.py`；认证后按模型原文“WebAllowed = roles 含 admin 或 ai-engineer。business-user 单独不准入；混合角色含任一准入角色则允许。”执行，缺角色返回 `auth.web_access_denied`，保持拒绝先于下游访问和必要的 trace_id / tenant_id 关联。
- [X] T023 [US1] 在 T014 / T016 / T018 红测后修正 `services/bff/src/contexture_bff/api/deps.py`、`services/bff/src/contexture_bff/adapters/keycloak.py` 与 `services/bff/src/contexture_bff/api/auth.py` 的刷新 / 登录回调处理；callback 按 code + state 或 error + state 显式校验，先验证并一次性消费 state，成功才换码；login / callback 可处理的失败按 `specs/004-web-shell/contracts/bff-session.md` 返回固定 `/auth/error` 的安全 303，JSON API 保持状态码错误、不作登录重定向。复用 SessionRecord 既有字段，遵守模型原文“只在 BFF 会话库保存，浏览器仅持 HttpOnly ctx_session Cookie。”、“刷新成功更新令牌并按现有会话寿命规则使用，不扩大 expires_at。”、“明确 invalid_grant / 会话过期：删除或判定无效，401。”及“暂时网络 / 身份服务故障：保留记录，返回 502，不使用过期令牌提供业务内容。”；内部错误不吞成 401，不把失败创建为新会话。
- [X] T024 [US1] 在 T016 / T018 红测后修改 `services/bff/src/contexture_bff/api/auth.py` 的 logout，遵守模型原文“退出：删除该 session_id，Cookie 过期，不通知其他客户端 / IdP 全局会话。”，无会话幂等 204、删除失败 500；移除调用 Keycloak logout 的副作用，不读取或请求 Paperclip，保留原 Cookie 安全边界。
- [X] T025 [US1] 在 T019 红测后修改 `apps/web/src/api.ts`，以现有生成客户端请求 Me，保留响应状态并安全处理非 JSON / 网络故障；logout 检查响应成功且符合 204 契约后才完成，失败可重试；登录仅走既有 BFF OIDC 入口，携带安全站内路径与查询，浏览器不保存身份令牌或服务凭证。
- [X] T026 [US1] 在 `apps/web/src/auth/session.ts`、`apps/web/src/auth/SessionProvider.tsx`、`apps/web/src/auth/SessionBoundary.tsx` 实现 Me 缓存及 checking → authenticated / anonymous / forbidden / unavailable；CurrentUser 从生成 Me 归一：tenant_id（string）“服务端部署上下文；单租户，不从页面输入获取”，user_id（string）“受信身份主体；不能为空，不可由用户头覆盖”，display_name（string / null）“为空时回退 user_id；长文本截断但完整可读”，roles（string[]）“来自验签后的 realm_access.roles；缺失视为空”。把线上缺省 display_name 归一为 null、roles 归一为空数组，不强制断言 optional 字段已存在；落实“logoutPending 是动作状态，不新建数据库会话。若退出响应丢失，可再次幂等退出确认。”，清缓存 / 取消旧请求、身份重试有界、焦点 / 页面恢复重新核验，不用缓存角色取代 BFF。
- [X] T027 [US1] 在 `apps/web/src/i18n/zh-CN.ts`、`apps/web/src/layout/AccountMenu.tsx`、`apps/web/src/pages/HomePage.tsx` 实现真实账号 / 角色、完整长身份读取、问候及退出；新增 `apps/web/src/pages/LoginFailurePage.tsx` 复用 PageState，采用 LoginFailurePresentation 的 reason = cancelled / invalid_response / unavailable / internal（缺失或未知归 invalid_response）、可选 32 位十六进制 trace_id、安全站内 return_to（缺失 / 非法 / 指向自身归 /home），只显示固定中文说明及重新登录 / 返回首页，不显示 code / state / token / error_description；主页使用最小共享 Panel，文案集中管理，不写死原型身份。
- [X] T028 [US1] 在 `apps/web/src/main.tsx` 与 `apps/web/src/App.tsx` 接入唯一会话 Provider，公共 `/auth/error` 在会话门禁前匹配，只渲染恢复说明；其他业务路由保持受保护，`/` 默认导向 `/home`，保留 `/objects/:typeKey`。重新登录携带安全目标并生成新 state / PKCE，返回首页正常鉴权，退出成功停留匿名入口不自动 SSO；适配 `apps/web/src/__tests__/objects-page.test.tsx` 的装配，确保旧设备页读取不回退。
- [X] T029 [US1] 运行 T014–T020 新增用例、BFF 全部单元 / 契约 / 集成、py-core 身份回归和 Web 用例，真实环境演练独立 US1；在 `specs/004-web-shell/evidence/us1-validation.md` 记录五组角色、直接接口拒绝、旧 Cookie、失败恢复、MCP / 网关通用业务身份未被收紧的证据及 2 分钟演练结果，不以尚未就绪的业务占位判定 US1 失败或伪造环境结果。

**Checkpoint**: US1 可独立使用与验证。MVP 包含真实身份、最小首页与账号、Web 门禁和本地退出；完整导航与 004 整体验收尚未完成。

## Phase 4: User Story 2 — 切换工作模块并调整页面空间 (Priority: P1)

**Goal**: 在 US1 的唯一身份边界内完成四个一级入口、首页二级菜单、页面空间调整、真实分期状态与复用示例。

**Independent Test**: 使用已准入身份，在四个一级入口及概览 / 审批中心之间操作，验证标题、路径、选中态、收起偏好、直达 / 刷新 / 前进 / 后退及未知路由；在 1280×720 和 1440×900、100% 缩放下用键盘完成核心操作。导航与占位不依赖搜索、Agent 或审批服务。

### Tests for User Story 2 — 先失败，再实现

- [X] T030 [P] [US2] 在 `apps/web/src/__tests__/navigation.test.tsx` 先写四个一级入口顺序、品牌、可读名称 / aria-current、概览与审批二级菜单、action 新建对话归属、标题与路径一致的测试；覆盖收起 / 展开与重复点击、切页保留 / 刷新重置、深链 / 历史导航、不存在页、旧设备不入菜单，禁止为资产或 Agent 生成假二级目录。
- [X] T031 [P] [US2] 在 `apps/web/src/__tests__/shell-pages.test.tsx` 先写首页指标 / 最近资产 / 待办布局与真实问候、四个未开放页、返回首页和长中文测试；断言缺数据不显示零 / 假日期 / 原型业务数据 / 开发编号，搜索与问 Agent 隐藏，进入这些页面不请求 OM、搜索、Agent、审批或执行接口。
- [X] T032 [P] [US2] 在 `apps/web/src/__tests__/ui-examples.test.tsx` 先写 `/__dev/ui` 的受保护开发示例测试，覆盖基础组件变体、五类状态的触发 / 结束 / 恢复、第二示例内容复用同一 Shell / 标题 / PageState、普通导航无示例入口；区分开发 / 测试模式与生产路由，生产未开放不能只靠隐藏导航。
- [X] T033 [P] [US2] 在 `tests/e2e/shell-navigation.spec.ts`、`tests/e2e/ui-examples.spec.ts` 先写真实已登录浏览器的路由 / 历史、收起 / 展开、两种尺寸、键盘 / 焦点 / 长内容和无横向溢出用例；按 `specs/004-web-shell/contracts/browser-validation.md` 更新 `tests/e2e/playwright.config.ts` 为 8080 生产组（排除 ui-examples，包含生产示例不存在断言），新增 `tests/e2e/playwright.ui.config.ts` 为 5173 开发组（只运行 ui-examples、webServer 启动 Vite），在 `package.json` 注册 e2e:ui；复用 T020 helper 先在 8080 真实登录后转至 5173，不新增 IdP 回调、不以 mock / skip 替代认证。

### Implementation for User Story 2

- [X] T034 [US2] 在 T030 红测后创建 `apps/web/src/layout/navigation.ts` 并补 `apps/web/src/i18n/zh-CN.ts`，定义 RouteEntry 的 id、label、path、module、secondaryItems、availability（shell / not_open）、isAction；落实模型原文：`新建对话是动作型入口，004 仍有独立占位地址；模块归 Agent，当前标题为“新建对话”。`以及“路径是当前位置唯一事实来源，菜单高亮和标题从路由派生，不另存独立 screen 导致不一致。”。
- [X] T035 [US2] 在 `apps/web/src/layout/AppShell.tsx`、`apps/web/src/layout/PrimaryNav.tsx`、`apps/web/src/layout/SecondaryNav.tsx` 与 `apps/web/src/layout/PageHeader.tsx` 实现一级栏、首页二级菜单、页头和可滚动内容区，复用 AccountMenu 与共享组件；遵守模型原文“菜单状态 secondaryOpen 是应用内 boolean，默认 true；路由切换保留，刷新重置，不存 localStorage。”，收起后保留有名称的展开操作，tooltip 覆盖聚焦与悬停，核心操作不受长内容遮挡。
- [X] T036 [US2] 在 T031 红测后完善 `apps/web/src/pages/HomePage.tsx`，新增 `apps/web/src/pages/NotOpenPage.tsx`、`apps/web/src/pages/NotFoundPage.tsx`，使用真实账号和“尚未接入 / 尚未开放”保留首页版式，提供各业务未开放说明与返回首页；不放假数量、会话、执行入口或 spec 编号，默认隐藏顶栏搜索与问 Agent，不新增业务请求。
- [X] T037 [US2] 在 `apps/web/src/App.tsx` 接入 AppShell、`/home`、`/assets`、`/agents`、`/agents/new`、`/approvals` 与兜底不存在页，保留 `/objects/:typeKey` 的准入保护；以嵌套路由保持一次会话边界与内存菜单偏好，校验 `apps/web/nginx.conf` 的 SPA 回落可支持深链 / 刷新，不另建导航或 Router 实例。
- [X] T038 [US2] 在 T032 红测后创建 `apps/web/src/pages/UiExamplesPage.tsx`，通过 `apps/web/src/App.tsx` 与 `apps/web/vite.config.ts` 按 `specs/004-web-shell/contracts/browser-validation.md` 的构建边界注册 `/__dev/ui`：仅开发 / 测试构建启用且受保护，标准生产 build 不注册；落实“组件示例使用明确的演示数据，不把示例状态发布为真实业务结果。”，包含可复用接入的独立演示内容，不以 URL / localStorage / 用户参数开启生产路由。
- [X] T039 [US2] 运行 T030–T033 测试及 US1 回归，分别用生产构建和受保护开发构建检查核心导航、组件示例恢复、两种尺寸、键盘、中文长文案、无横向溢出与无业务请求；在 `specs/004-web-shell/evidence/us2-validation.md` 记录命令、构建模式、截图 / trace 与结果，修复时先补失败测试再复验受影响路径。

**Checkpoint**: US2 可依现成准入会话独立验证；两个故事共用身份和组件，不依赖后续业务服务。D1 / D2 仍须完成最终说明、门禁和验收。

## Phase 5: Polish & Cross-Cutting Concerns — 门禁、接入说明与验收

**Purpose**: 汇总两个故事和公共交付，先完成全部自动化验证，再编写独立手动验收文档。

- [X] T040 更新 `apps/web/README.md` 的新页面接入说明，以 `apps/web/src/pages/UiExamplesPage.tsx` 给出复用会话、布局、导航、标题、中文和公共状态的可重复演练；同步 `README.md`、`services/bff/README.md` 与 `specs/004-web-shell/quickstart.md` 的实际命令、准入角色、本地退出、开发 / 生产示例区别及旧设备显式入口，不回写 001 已验收记录、不把规划命令称为执行结果。
- [X] T041 在 `.github/workflows/ci.yml`、`Makefile`、`apps/web/vite.config.ts`、`packages/ui/vite.config.ts` 接入 Web / UI 行覆盖率 ≥80% 和新增 / 修改行 ≥80% 的报告与门禁，所需工具按 `pyproject.toml` / `package.json` 及锁文件固定；保留 Python 真实集成、API 生成一致性、oasdiff、组件和补丁检查。按 `specs/004-web-shell/contracts/browser-validation.md` 让 make e2e 在既有只读集群 / 生产浏览器用例后执行 pnpm e2e:ui（003 双规模重建组保留为显式 e2e-mock-data），任何一组失败均非零退出；用临时覆盖不足输入证明覆盖率门禁失败，若新增自建校验代码先补行为失败测试。
- [X] T042 在 `.github/workflows/ci.yml` 与 `apps/web/Dockerfile` 补 Web 交付物和前端依赖的 SBOM、许可与漏洞扫描，复用 `tools/license_check.py`、`tools/license-allowlist.yaml` 及现有扫描工具；SBOM 必须覆盖实际打包的 npm 依赖，不能只有最终 nginx 镜像系统包。保持 BFF 扫描，记录待人工核对的许可与固定版本，不以修改 allowlist / 漏扫前端依赖消除失败。
- [X] T043 在 `specs/004-web-shell/evidence/validation.md` 记录并通过 `make lint`、`make test`、Web / UI test:coverage 与 build、ts-api check、`make components-check`、`make patches-check`、oasdiff、镜像构建及 T041–T042 门禁；核对变更行覆盖率、Web / UI 报告和测试先于实现的提交顺序，整理需评审的契约兼容性记录，不关闭失败检查或以总覆盖率掩盖未测新增代码。
- [X] T044 使用现有本地部署和已核对种子数据运行 `make e2e`，依据 `specs/004-web-shell/contracts/browser-validation.md` 分别记录 pnpm e2e:browser（8080）和 pnpm e2e:ui（5173）的结果到 `specs/004-web-shell/evidence/validation.md`；确认新生产镜像的示例路由不存在、真实登录开发示例可恢复、旧设备 OM / Doris / 网关 / trace 链路通过，不以全 skip 视为通过、不改共享 realm / Paperclip、不重建 003 数据；环境阻塞与特性失败分别记录。
- [X] T045 复核 `specs/004-web-shell/research.md`、`specs/004-web-shell/contracts/embed-readiness.md` 与 `specs/004-web-shell/plan.md` 的四主题证据对应本次实际宿主依赖，补清命令、限制和 007 责任项；依赖或构建方案在后续实现中变化时先重跑受影响实测，再更新最终验证记录，不能沿用失效证据认定 SC-007 通过。
- [X] T046 在 T043–T045 完成后编写 `specs/004-web-shell/acceptance.md`：前置环境 / 身份 / 数据、可复制命令、30 分钟操作步骤与每步预期、US1 / US2 / D1 / D2 及 SC-001–SC-008 映射、全部自动化实测与覆盖率、环境限制、兼容性证据和待填写的验收记录；用户步骤限于正式页面的身份、导航、占位和使用体验；五组角色、公共状态、页面接入、兼容性与旧示例回归以开发侧工程证据覆盖，工程操作置于 quickstart，不要求用户逐项操作，不预填负责人“通过”。
- [X] T047 按 `specs/004-web-shell/acceptance.md` 只将正式产品页面操作交由产品负责人独立执行并填写日期、验收人、结果和问题；问题先补失败测试再修复，重跑受影响检查并更新验收记录，未获负责人实际确认不得代签或勾选本项。
- [X] T048 仅在 T047 实际通过后同步 `specs/004-web-shell/spec.md`、`specs/004-web-shell/plan.md` 和 `docs/Phase1-特性列表与开发计划.md` 的 004 状态与证据链接，保留 005 → 006 → 007 → 008 顺序、007 暂估与待验证项；依宪法保留 PR 评审、CI 全绿和非 squash 合并要求，本任务不自动提交、合并或部署。

## 2026-11-03 修订：主动登录重新认证（负责人已确认）

执行顺序为 T046 → T049–T052 → T053–T057 → T047 → T048；保留原任务 ID 和历史完成记录，不代签手动验收。

- [X] T049 更新根登录契约及 spec / plan / research / bff-session / ADR-0003；在真实 KeycloakOidc 单元、保持 SSO Cookie 的集成与真实浏览器中先复现缺少重新认证的失败，不以修改 FakeOidc 代替实测。
- [X] T050 KeycloakOidc 授权 URL 固定 prompt=login；不改退出、正常 Me / refresh 或前端会话模型。测试辅助支持保留同一身份会话，浏览器 helper 不再接受直接 SSO 通过。
- [X] T051 通过适配器 / BFF 回归、真实 Keycloak + PostgreSQL 集成、Web / UI 回归和生产 / 开发浏览器；验证错误密码、旧 Cookie、正确认证返回目标、取消恢复、正常刷新和 IdP 会话保留。重建本机 BFF，执行类型 / 契约 / 覆盖率与受影响镜像扫描，保留原门禁。
- [X] T052 同步 README / quickstart / acceptance，并在 evidence/validation.md 追加本次日期、实际结果、镜像与限制；旧验证保留为历史，T047 / T048 仍待负责人实际验收。

## 2026-11-03 修订：登录外观提案 B（已确认）

T053–T057 在 T047 用户验收之前执行，既有完成记录保留。

- [X] T053 更新原型确认与登录视觉约定；先写登录入口 / 帮助 / 安全目标、共享身份布局、真实 Keycloak 客户端主题隔离和视觉浏览器失败测试。
- [X] T054 从设计重建生产共享布局 / 静态资源及 LoginPage，接入匿名与登录失败页面，统一中文；不复用原型代码，不改变认证行为。
- [X] T055 通过官方父主题保留 Keycloak 原生表单 / 安全脚本，增加局部视觉扩展；完成主题资源打包 / 一致性检查、自带模式 ConfigMap 与 contexture-bff 专属主题配置，测试其他客户端不变。
- [X] T056 验证单元 / 契约 / 真实身份 / 浏览器、两种窗口与键盘、错误密码 / 密码显隐 / 重新认证、生产隐藏预览控件；检查覆盖率、lint、组件 / 补丁、打包一致性、离线资源与镜像，更新本机服务。
- [X] T057 同步用户验收中的正式登录体验及开发部署说明；追加实际证据与限制。用户无需访问开发组件或执行工程命令；T047 / T048 不代签。

## Dependencies & Execution Order

### Phase Dependencies

```text
T001 基线
  → T002 锁定上游构建 → T003 Vite 宿主实测 → T004 传输 / 身份依据
  → T005 依赖选择门禁
  → T006 契约及迁移前提 → T007 依赖 / 测试基础
  → {T008 原语红测 || T009 状态红测} → T010 原语 → T011 状态 → T012 构建集成
  → US1：T013 夹具 → {T014–T020 红测批次} → T021–T028 实现 → T029 独立验证
  → US2：{T030–T033 红测批次} → T034–T038 实现 → T039 独立验证
  → T040–T042 交付说明 / CI → T043–T045 全部验证与证据复核
  → T046 acceptance → T049–T057 修订验证 → T047 负责人验收 → T048 状态同步
```

- Phase 1 的失败 / 未执行不能被后续依赖调整“顺便验证”掩盖；T007 明确依赖 T005。T006 的版本兼容前提不成立时，先完成并评审迁移方案再进行受影响实现。
- Phase 2 完成后才开始故事的产品实现。两个故事同为 P1，但 US2 复用 US1 的身份基础，因此默认串行，不声称两个完整故事可无依赖并行。
- US1 内 T021 依赖 T017；T022 依赖 T014 / T015；T023 依赖 T014 / T016 / T018，T024 依赖 T016 / T018；T025–T028 依赖 T019 / T020，且端到端联调在后端就绪后进行。
- T023 与 T024 共享 auth.py，T022 与 T023 共享 deps.py，必须串行；US1 / US2 的 App.tsx、main.tsx、中文入口和 HomePage.tsx 也按阶段交接。
- US2 内 T034–T035 依赖 T030；T036 依赖 T031；T037 汇合布局与页面且保留公共 `/auth/error`；T038 依赖 T032 和 T037；T033 的双配置浏览器用例在 T039 分组验证，T041 将两组串接到 make e2e，T044 完成最终环境验证。
- T041 与 T042 共享 CI 文件，必须串行。T045 若触发重测或实现修复，受影响的自动化验证重新通过后才可写 T046 的最终结果。
- T047 的确认来自负责人；有问题则继续 TDD 修复和复验，不以生成 acceptance 或本清单代表完成。

### Within Each User Story

1. 按已评审契约先写行为测试，保存真实失败原因；测试先于对应实现提交。
2. 模型 / 公共库 → 服务端依赖与接口 → 客户端状态与页面 → 路由集成；每步只实现对应失败测试要求。
3. 单元 / 契约测试通过后，以真实依赖集成和浏览器用例完成独立验证；环境故障不伪装为功能通过。
4. 修改公共认证库时复验 MCP / 网关既有业务身份，不扩大 Web 角色收紧范围。

### Parallel Opportunities

- 基础批次：T007 完成后，T008 与 T009 修改不同测试文件，可并行。
- US1 测试批次：T013 及共同基础完成后，T014–T020 的文件互不重叠，可并行编写与运行相应红测；真实依赖夹具必须隔离资源。
- US2 测试批次：US1 及共同基础完成后，T030–T033 可并行；实现共享路由 / 文案文件不标 `[P]`。
- `[P]` 是未来执行安排，不表示本次启动了多个代理或执行了任务。

## Parallel Example: User Story 1

共同前置：T012、T013 完成，根契约已更新。

```text
Task T014: services/bff/tests/contract/test_session_contract.py — 接口契约红测
Task T015: services/bff/tests/unit/test_web_access.py — 角色与绕过红测
Task T017: packages/py-core/tests/test_auth.py — JWKS 分类与通用身份回归
Task T019: apps/web/src/__tests__/session.test.tsx、api.test.ts — 前端状态与请求红测
```

各任务不修改共享夹具；发现需要新增公共夹具时先串行补到 T013 的测试设施，再恢复并行。实现任务只在对应红测确认后开始。

## Parallel Example: User Story 2

共同前置：T029 完成，组件和身份边界可复用。

```text
Task T030: apps/web/src/__tests__/navigation.test.tsx — 路由 / 菜单行为
Task T031: apps/web/src/__tests__/shell-pages.test.tsx — 主页 / 未开放页面
Task T032: apps/web/src/__tests__/ui-examples.test.tsx — 开发示例与模式边界
Task T033: tests/e2e/shell-navigation.spec.ts、ui-examples.spec.ts — 浏览器场景
```

浏览器登录 helper 复用 T020 产物，不在并行批次中同时重写 helper、App.tsx 或共享文案。

## Implementation Strategy

### MVP First — US1

1. 完成基线、隔离嵌入实测及宿主选择门禁，不把正式 Agent 接入前置到 004。
2. 完成契约、依赖和最小公共 UI；先交付 US1 的真实登录、身份、最小首页与本地退出。
3. 通过 T029 独立验证后可演示身份闭环；这只是 MVP 检查点，不能据此标记整个 004 完成。

### Incremental Delivery

1. US1 提供可信身份边界；US2 在同一边界内补齐导航、首页版式、未开放页面及开发示例。
2. 完成 CI、接入说明、兼容性报告与独立验收，负责人实际验收后再同步完成状态。
3. 后续按 005 → 006 → 007 → 008 推进。004 不导入测试元数据、不连接实际数据源、不创建 Agent 会话、不处理审批、不开放终端 / 定时执行。
4. 007 的真实身份桥接、助手 / 工作台同会话、资产上下文与来源、MCP 凭证、执行拒绝只作交接；007 计划与工期定稿前另行验证，012 负责安全执行与恢复加固。

## Coverage & Traceability

| 规格要求 | 主要任务 | 独立判据 / 验证 |
| --- | --- | --- |
| FR-001–FR-004、FR-017：身份、角色、安全返回、故障与退出 | T006、T013–T029、T049–T052 | SC-001；五组 Cookie / Bearer 角色、真实身份 / 会话及浏览器退出 |
| FR-005–FR-008：入口、二级、路由与空间 | T030、T033–T035、T037、T039 | SC-002；标题 / 高亮 / 路径一致，偏好与历史导航 |
| FR-009–FR-011：首页及未交付边界 | T027、T031、T036、T039 | SC-003；无假数据、开发编号、业务调用 |
| FR-012–FR-016：视觉、状态、桌面、可访问性与中文 | T008–T012、T019、T027、T030–T039 | SC-004 / SC-005；两种尺寸、键盘、状态恢复、长中文 |
| FR-022：确认后的登录品牌视觉、客户端隔离与原生认证 | T053–T057 | 两尺寸真实登录、帮助 / 显隐键盘、主题范围、资源打包一致性 |
| FR-018：开发示例与新页面接入 | T032、T033、T038–T040 | SC-006；受保护开发示例复用同一 Shell，生产路由不存在 |
| FR-019：四主题提前兼容性报告 | T002–T005、T045 | SC-007；实际构建 / 挂载证据，代理 / 身份依据与 007 责任项 |
| FR-020：001 设备回归 | T013、T020、T028–T030、T037、T044 | 准入身份的旧读取链路及 trace 不回退，不入产品菜单 |
| FR-021：独立验收 | T043–T048 | SC-008；自动化先完成，30 分钟负责人复验，记录实际结果 |
| 宪法 I / II / III / VI：TDD、契约、覆盖率、锁版与许可 | T001–T007、各红测任务、T041–T045 | 非 squash 测试先行记录、差异覆盖率 ≥80%、真实依赖、SBOM / 扫描与补丁检查 |

## Notes

- 原 48 项任务（本次追加 T049–T057 共 9 项）：Setup 5、Foundational 7、US1 17、US2 10、Polish 9；13 项 `[P]`，全部为不同文件的测试批次。
- 数据模型无新增持久化实体；Existing SessionRecord 的 user_id、access_token、refresh_token、id_token、access_expires_at、expires_at 继续只在 BFF 会话库保存，浏览器仅持 HttpOnly ctx_session Cookie。
- 本清单保留实测、契约评审、自动化与负责人验收门禁；尚未执行的项目全部保持未勾选。实际任务调整需同步依赖和覆盖映射。


### 2026-11-03 用户验收文档修正

T046 的用户操作范围已按反馈收敛到正式产品页面。开发组件 / 故障模拟等步骤迁到 quickstart，
工程结果及质量门禁保持，T047 由用户确认产品体验，不要求用户验收开发工具。无新增实现或测试执行，未代签通过。


### 2026-11-03 登录文案修订

- [X] T058 按负责人指定内容同步共享登录文案、企业身份主题、子原型 / 预览和 spec；第三项支柱保持。更新既有选择器，验证 Web / UI、两尺寸真实登录、主题副本及本机部署；证据见 validation.md。无认证或能力范围变更，T047 / T048 保持待确认。

- [X] T059 将登录标题按负责人修订为“构建企业AI Ready数据”，同步原型 / spec / 主题及本机页面，执行 Web 既有测试和两尺寸真实登录验证；其他文案保持，证据见 validation.md。

- [X] T060 按负责人修订第二项支柱标题与描述，同步共享文案、原型 / spec / 主题和本机页面；UI 既有测试、两尺寸真实登录及两端实际文案检查通过，证据见 validation.md。


## 2026-11-03 验收关闭

负责人明确确认“spec04验证完了，可以关闭了”。据此登记 T047 验收通过，并完成 T048 的
spec / plan / 开发计划状态同步。T001–T060 全部完成；上文带日期的待验收描述为当时记录，
以本节及 acceptance.md 的最新确认结果为准。PR、远端 CI、独立评审和非 squash 合并继续遵循宪法，未自动执行。
下一特性为 005 源系统元数据采集，尚未创建规格或开始实现。
