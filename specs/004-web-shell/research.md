# Research: 004 外壳、身份与未来嵌入接缝

2026-10-31 初稿；2026-11-01 方案 B 静态研究；2026-11-02 已完成 T001–T005 实施前验证，当前结论以 R14 与证据附件为准。以下历史研究区分“代码已确认”“设计决定”“尚待实测”；未安装依赖或修改上游。
Omnigent 证据固定为 v0.18.0（`a8676d23e88df7918f4f8ef1c7c4e3186e710354`），不以当前上游最新版本替代本工程锁定版本。

## R1. 外壳只读既有身份，不新增业务服务

**Decision**: 保留 Web / BFF / py-core / ts-api 分层，新增共享 UI 包，不建设外壳配置后端。
**Rationale**: 现有 `/me` 已提供 tenant_id、user_id、display_name、roles；nginx 已配置 SPA 回落，Vite 已有同源 `/bff` 代理。
**Alternatives considered**: 新建 shell 服务或每页重复会话管理均增加无必要边界；不采用。
**Evidence**: `apps/web/src/main.tsx`、`apps/web/nginx.conf`、`apps/web/vite.config.ts`、
`services/bff/src/contexture_bff/api/me.py`、`contracts/openapi/bff.yaml`。

## R2. Web 角色门禁属于 BFF，不属于通用认证库

**Decision**: require_web_context 先调用通用 current_context，再校验 admin / ai-engineer；应用到 Me 与 object 路径。
**Rationale**: 现有代码只验令牌，不验角色；业务用户仍应能使用网关 / MCP，不能把全局 Authenticator 改成 Web 专属门禁。
**Alternatives considered**: 只前端隐藏入口不能阻止直接请求；全局改变 JWT 夹具 / auth 库会破坏其他客户端；均不采用。
**Evidence**: `services/bff/src/contexture_bff/api/deps.py`、`api/me.py`、`api/objects.py`、
`packages/py-core/src/contexture_core/auth.py`；角色来源为已签名令牌 `realm_access.roles`。
**Migration**: BFF 单测、契约测试、真实登录测试、浏览器 demo 原先有 business-user / user1 成功路径，需针对 Web 切换成 engineer1。

## R3. 退出只清除织境会话；不能把退出失败当成功

**Decision**: 本地存储删除 + Cookie 过期，成功 204，取消 BFF 的 IdP session logout 副作用；匿名页显式提供登录操作。
2026-11-02 负责人明确确认不调用 IdP logout；该选择已写入 spec 澄清与 FR-004，旧的上游退出失败措辞已移除，实际实现仍待 T024。
**Rationale**: 用户明确 Paperclip 与织境登录无关；当前 auth.py 仍调用 `oidc.logout(refresh_token)`，
适配器会向 Keycloak `/logout` 发请求，不能假定其不会影响共享 IdP 会话。客户端 fetch 也未检查非 2xx 就跳回首页。
**Alternatives considered**: 保留 provider logout 与应用内退出语义不一致；退出后自动跳 SSO 会立即重建会话，掩盖退出结果；均不采用。
**Evidence**: `services/bff/src/contexture_bff/api/auth.py`、`adapters/keycloak.py`、`apps/web/src/api.ts`。
**Scope**: 不变更共享 realm，不读取 Paperclip，不用其运行状态作验证条件；旧 Cookie 不能复用，显式新登录仍可 SSO。

## R4. 会话无效、Web 拒绝和身份依赖故障必须分开

**Decision**: 401 结束无效会话；403 显示无权限；502 保留会话记录并允许重试；500 显示内部故障。
**Rationale**: 当前前端 catch-all 转 anonymous，刷新异常全部删除会话，JWKS HTTPError 又被归入 invalid_token；均与 spec 不符。
**Alternatives considered**: 网络超时自动重登会造成登录循环并掩盖故障；允许过期 token 继续使用违反身份要求。
**Evidence**: `apps/web/src/App.tsx`、BFF `session_or_bearer()`、py-core `TokenVerifier.verify()`、`errors.py`。
**Precision**: 仅明确 invalid_grant / 已撤销身份终止会话；异常分类保留 Authlib / httpx 的原因，不吞掉任意异常。

## R5. 共享 UI 和工具链

**Decision**: `packages/ui` 使用 React peer dependency、Tailwind tokens、必要 Radix 原语；宿主仍为声明式 Router。
身份请求用独立 QueryClient；不为了五种组件状态引入完整组件管理服务。
**Rationale**: 符合 ADR-0003，未来可被其他前端包复用。基础组件自主编写，不复制 Omnigent 或 OM UI / 原型源码。
**Alternatives considered**: Ant Design 增加版本 / 样式冲突；把组件都写到 App.tsx 难复用；Storybook 平台超出当期需求。
**Primary references**:
- [React Router 声明式路由](https://reactrouter.com/start/declarative/routing)：布局路由、Outlet 与嵌套路由；实际版本以锁定上游 7.18.2 为准，而非文档 latest 版本。
- [Tailwind Vite 安装](https://tailwindcss.com/docs/installation/using-vite)：构建插件与 CSS 导入；依赖用上游锁定的 4.3.1，不用远程运行时 CDN。
- [Vite library mode](https://vite.dev/guide/build#library-mode)：ESM / CSS 输出及共享外部依赖模式，不证明具体 Omnigent 宿主已运行成功。

## R6. Omnigent 官方嵌入证据与宿主版本选择

**Decision**: 宿主目标 React / ReactDOM 18.3.1、react-router / react-router-dom 7.18.2；先做隔离验证再改产品依赖。
**Rationale**: 锁定源码有 `build:embed`（Vite）、`src/embed.tsx`（不新建 root / Router）、
`vite.embed.config.ts`（React / Router 外部依赖、ESM chunks、作用域 CSS）。上游根 `pnpm-lock.yaml` 锁定上述 React / Router，
Tailwind 4.3.1、Radix 1.6.3、Query 5.101.2；宿主现为 React 19 / Router 8，存在实际差异。
嵌入输出是供下游消费的中间产物，现有外部依赖和 Worker 处理针对 rspack 宿主；Vite 构建命令存在不等于 Vite 宿主已兼容。
**Alternatives considered**: 照抄注释中的 Router 6.4.1 与实际 manifest 冲突；双份 React 容易破坏 hooks 与路由上下文；
改用 iframe 改变既定官方嵌入方案，均不默认采用。
**Evidence**: `third_party/omnigent/src/web/package.json`、`vite.embed.config.ts`、`src/embed.tsx`、
`third_party/omnigent/src/pnpm-lock.yaml`（web importer）；提交 `a8676d23e88df7918f4f8ef1c7c4e3186e710354`。
**Current verification**: 2026-10-31 调查时没有上游 node_modules 或 dist-embed；2026-11-01 文档修订未安装依赖，尚无真实构建 / 浏览器运行数据。
“Vite 构建入口存在”已确认，“产物可以在织境宿主完整运行”仍待实测，不得混同。

## R7. 传输接缝存在，安全身份桥接不等于传入 Bearer

**Decision**: 007 经 BFF 注入官方 fetcher / WebSocket URL 接缝；必须先验证签名身份桥接，剥离浏览器身份头。
**Rationale**: `web/src/lib/host.ts` 提供 fetcher / resolveWebSocketUrl；identity.ts 查询 `/v1/me`，
并可能从浏览器缓存生成 X-Forwarded-Email。`omnigent/server/auth.py` 的 OIDC / accounts Bearer 路径校验
其自身 cookie_secret 签发的 HS256 会话令牌，不是通用 Keycloak 访问令牌校验。浏览器用户头不能作为授权事实。
服务端提供 `AuthProvider` 与 `create_app(auth_provider=...)` 自定义接缝，可优先验证独立扩展，生产启动接线与身份映射尚未实测。
**Alternatives considered**: BFF 简单转发用户头或伪造“已验证 Bearer 支持”违背宪法；不采用。
**004 conclusion**: 身份桥接是已识别的 007 集成阻塞；004 无正式上游连接，不受此运行依赖阻塞。
007 必须选择经签名身份校验的官方认证 / 扩展方案，必要补丁遵循宪法 VI，不能以本报告视为已解决。
**Evidence**（均相对 `third_party/omnigent/src/`）: `web/src/lib/host.ts`、`web/src/lib/identity.ts`、`omnigent/server/auth.py`、`omnigent/server/app.py`。

## R8. 侧栏配置并不包含隐藏终端的权限控制

**Decision**: 004 不挂载正式 Omnigent；007 另验服务端执行能力拒绝和 UI 关闭路径，012 才开放安全执行。
**Rationale**: `web/src/appConfig.ts` 的 SidebarConfig 只涉及轮询、分享和分页等参数，无通用 hide sidebar / terminal 参数。
embed 的 host config、QueryClient 和身份缓存还含模块级状态；007 不能无条件挂载两份不受控工作台来实现共享对话。
**Alternatives considered**: 把 CSS 隐藏或 sidebarConfig 当授权，不能阻止接口执行；不采用。
**Follow-up**: 007 采用同一服务端会话的两种展示：织境轻量助手与完整嵌入工作台；切换与实时状态需实测，不读取上游私有 store 实现同步。

## R9. 契约、回归和覆盖率

**Decision**: 根 OpenAPI 保留路径及 Me 字段集合，显式列出错误与退出 / 角色政策；实施前进行行为兼容评审。
2026-11-02 已将 Me.display_name 的根 Schema 校正为可缺省 string / null，并重新生成类型，与 BFF 已有返回一致。
登录导航的取消 / 失败拟采用 303 返回织境恢复页，JSON API 继续原错误分类；参数与恢复契约见 bff-session.md，实施前一并核对消费者。
**Rationale**: 安全策略变化不能只改前端测试。现有 CI 只有 BFF 镜像 SBOM 与 Python 行覆盖门禁，Web / UI 需补齐。
**Alternatives considered**: 全局替换 business-user 默认夹具会破坏网关业务权限回归；跳过 oasdiff 或伪造所有已有测试已适配不采用。
**Evidence**: `contracts/openapi/bff.yaml`、`.github/workflows/ci.yml`、`services/bff/tests/bff_fakes.py`、
`services/bff/tests/integration/test_auth_flow.py`、`tests/e2e/demo.spec.ts`、`tests/support/jwt.py`。
**Maintenance note**: 2026-11-01 已同步 ADR-0009、`apps/web/README.md`、`third_party/omnigent/UPSTREAM.yaml` 与 `PATCHES.md`，
当前规则为官方嵌入、007 集成与 012 运行时扩展；旧复制方案只在 ADR 历史段落保留废止记录。

## R10. 方案 B：织境主应用与 Omnigent 工作台分工

**Decision**: 负责人确认方案 B。织境拥有导航、账号、业务页面与轻量页面助手，完整 Agent 工作台官方嵌入；
前后端必要定制按配置 → 官方扩展点 → 最小补丁处理。004 的用户故事、spec 与原型范围不变。
**Rationale**: 资产、治理、审批与上下文是持续扩展的核心能力；两方案都需要开发这些页面。方案 B 延续 001 的 Web / BFF，
使 006 的搜索独立于正式 Agent 集成交付，同时保留 Omnigent 完整开发工作区。
**Alternatives considered**: 方案 A 以 Omnigent 为主应用，可较快复用原生会话与开发工作区；官方插件能力有限，
承载织境业务需新增通信或页面接口。受控扩展不必然是深度分叉，但主导航与业务布局更依赖上游，本期不采用。
**Evidence**: [ADR-0003](../../docs/adr/0003-前端架构与管理端策略.md) 2026-11-01 修订；下列 R11–R13 的锁定源码证据。
**Current verification**: 这是已确定的架构选择，尚无构建、身份或同会话联调通过记录。

## R11. 官方嵌入、品牌与浏览器插件的边界

**Decision**: 整页工作台采用 `OmnigentApp`；品牌使用服务端 `branding`，主题明暗 / 路由 / 传输使用对应宿主接口；
工作台先保留默认样式，中文化、导航裁剪、业务消息渲染单独核查。
**Rationale**: `OmnigentAppProps` / `OmnigentHostConfig` 未提供现成 pageContext、业务结果 renderer 或精简聊天布局参数。
`sidebarConfig` 只控制轮询、共享、分页等；品牌 app_name / logo / heading 由 `/v1/info` 暴露，不能统称为嵌入 props。
浏览器插件 V1 是无网络访问的隔离 iframe，不能直接请求 BFF 或访问宿主 React 树；SDK 只有导航、主题、存储、会话摘要与项目等能力。
导航插槽固定，`when` / 命令 / activation_events 仅为预留元数据，不构成运行时角色控制。
**Alternatives considered**: 把资产搜索做成无需修改宿主的普通浏览器插件，缺少业务数据通信能力；
将完整工作台强行作为紧凑助手，仍缺上下文、布局和结果组件接缝，均不默认采用。
**Evidence**（相对 `third_party/omnigent/src/`）: `web/src/embed.tsx`、`web/src/lib/host.ts`、`web/src/appConfig.ts`、
`omnigent/server/server_config.py`、`web/src/lib/branding.ts`、`docs/extending/extensions.md`、`browser_extensions.md`、`extension_manifest.md`（后两者同目录）。

## R12. 官方客户端与同会话延续

**Decision**: 007 的轻量助手经 BFF 优先复用官方 `omnigent-client` / 已发布 API；助手和工作台关联同一个服务端会话 ID，
消息 / 运行状态以 Omnigent 为准，不新建会话正本，不复制前端私有 store 或 SDK。
**Rationale**: 官方 Python 客户端提供会话、消息与 HTTP / SSE 事件和语义块；会话快照 + 实时流可作为互通基础。
SSE 不回放历史，恢复需读快照并处理竞态与去重；客户端存在发送、取消等能力不代表当前 BFF 已接通。
SDK v0.18.0 精确依赖同版 `omnigent` 包，007 需检查 BFF 依赖体积、构建与许可证；`sdks/ui` 是终端 UI SDK，不是 Web 组件库。
**Alternatives considered**: 挂载两份完整工作台并依赖全局状态同步，或让助手另建不关联的对话，均不满足受控的同会话交互。
**Evidence**（相对 `third_party/omnigent/src/`）: `sdks/README.md`、`sdks/python-client/README.md`、`sdks/python-client/pyproject.toml`、
`sdks/python-client/omnigent_client/_sessions_chat.py`、`omnigent/server/routes/sessions/routes_events.py`、`web/src/embed.tsx`。
**Follow-up**: 007 计划与工期定稿前实测资产提问、来源、切换、消息去重、取消、重连与退出；四类结果先由织境助手与业务页面渲染。

## R13. 会话 MCP 配置与凭证生命周期

**Decision**: 将用户识别与 Agent 下游委托分别验证；007 明确短期凭证注入与失效处理，012 完成续期 / 执行恢复加固。
不能以静态 MCP header 声称实现委托生命周期，也不将有效访问令牌作为长期 Agent 配置保存。
**Rationale**: v0.18.0 会话 MCP 修改接口要求可编辑的会话级 Agent 与 owner 权限，会重写 Agent 包；
`_apply_headers` 将 headers 写入 YAML。内置 Agent 不能通过该接口修改，配置方式与动态令牌接缝都需联调。
**Alternatives considered**: 直接把一次交换得到的令牌写入配置并长期复用，不能满足失效、续期和恢复要求；不采用。
**Evidence**: `third_party/omnigent/src/omnigent/server/routes/session_mcp_servers.py`（`_editable_agent`、`_mutate_bundle`、`_apply_headers`）。
**Current verification**: 仅确认接口约束与存储行为；未执行真实 MCP 挂载、签名身份桥接或凭证续期实验。

## R14. 2026-11-02 实测与当前宿主选择（T001–T005）

**Decision**: 前置门禁通过。采用已验证的 React / ReactDOM 18.3.1、react-router / react-router-dom 7.18.2、宿主 Vite 8.3.4；上游构建继续使用自己的冻结 Vite 8.1.0，不强制改其锁文件。允许进入 T006 / T007。

**Actual results**:

| 主题 | result | 证据 / 限制 | ownerFeature |
| --- | --- | --- | --- |
| 官方嵌入与宿主构建 | runtime_pass | [构建](evidence/embed-build.md)；Node 24 首轮与 Node 22.20.0 复核均通过 | 004 |
| 共享依赖 / 路由 / 浏览器 | runtime_pass | [运行](evidence/embed-runtime.md)；深链、刷新、历史、scope / portal、卸载、静态资源、两个模块 Worker 启动；不代表真实文件操作 | 004 |
| HTTP / WS 接缝 | runtime_pass | [边界](evidence/embed-boundaries.md)；隔离代理、流取消、401 和 WS 握手 / 关闭，不是产品代理 | 004 |
| 用户识别与签名边界 | static_confirmed | AuthProvider / create_app 存在；自身 HS256 会话不是 Keycloak 通用 Bearer 验证 | 004 |
| 真实身份、SDK 同会话、MCP、执行拒绝 | not_run | 明确交接 007；不计作当前运行通过 | 007 |

每项 upstreamCommit、hostDependencyVersions、topic、procedure、result、evidenceLocation、limitations、ownerFeature 均见 [compatibility.json](evidence/compatibility.json)。

**Blocking resolution**: 网络受限导致包管理器签名引导失败，获得联网权限后成功；保留签名校验和冻结上游锁文件。临时 WS 夹具遗漏工作台自发连接路径时超时，补齐代理覆盖后全套通过。其余试跑中的夹具 / 选择器校正均已复测；没有通过修改上游或禁用检查解决问题。当前没有阻塞宿主依赖选择的未完成关键实测。

**Limitations**: 上游 CSS highlight 警告及宿主大模块警告仍保留；007 需评估加载预算、模块级状态、真实认证和能力控制。本机截图仅留临时目录，配置 / 锁文件 / JSON 证据可重建。004 产品实现与真实身份 / 集群回归尚未执行。


### T045 实现后复核（2026-11-02）

实际 Web 宿主锁定 React / ReactDOM 18.3.1、react-router / react-router-dom 7.18.2、Vite 8.3.4、pnpm 11.20.0，
与隔离试验组合相同。Docker 的 Node 22.23.4 / npm 12.2.1 构建、生产导航与开发示例真实浏览器验证通过。
未修改 Omnigent 源码 / 锁文件，未增加正式代理；原有四主题证据仍有效。007 的真实签名身份桥接、
SDK / 工作台同会话、MCP 凭证、执行能力服务端拒绝仍为 not_run，007 定计划前必须分别实测。
详细当前结果与限制见 [最终验证](evidence/validation.md)。


## R15. 2026-11-03 主动登录要求重新认证

**Decision**: 负责人确认改造方案后，BFF 生成所有用户主动登录的 Keycloak 授权 URL 时固定 prompt=login。
保留 R3 的应用内退出，不调用 IdP logout。此项替代 R3 中“显式新登录仍可 SSO”的交互描述。
**Rationale**: 用户退出后重新点击登录应有明确的认证步骤；企业 SSO 的有效性与本次主动登录是否要求认证分别处理。
**Implementation**: 仅修改 KeycloakOidc 授权 URL 生成；无前端状态 / 协议签名 / 会话数据迁移。正常 refresh 保持。
**Evidence**: [Keycloak 官方说明](https://www.keycloak.org/docs/latest/server_admin/) 的 prompt=login 重新认证规则；
实际结果在 evidence/validation.md 按日期追加。当前本地为密码表单，未来认证方式由 IdP 配置决定，不承诺所有 IdP 都使用密码。


## R16. 2026-11-03 登录视觉与身份服务主题

**Decision**: 负责人确认浅蓝方案 B。产品入口与企业认证页共享自主实现的静态资源及中文文案；
入口仍经 BFF 跳转，密码只由原生 Keycloak 表单处理。主题继承官方 keycloak，使用官方客户端
`login_theme` 属性限定到 contexture-bff，不改变共享 realm 或 Paperclip 的状态。
**Rationale**: 统一进入产品时的视觉，同时保留企业身份服务的表单、安全脚本、账号切换及原有分步认证。
没有新增库、服务或上游补丁；不复制原型实现及上游 FreeMarker 模板。
**Delivery**: 静态生成 values 由 components-check 校验，ConfigMap 只读挂载并以内容校验和更新；
离线交付直接包含该副本。外部身份服务的安装 / 缓存与持久化限制见 extensions/keycloak/README.md。
**Evidence**: [Keycloak 官方主题说明](https://www.keycloak.org/ui-customization/themes)；
对照锁定 26.8.0 原生表单 / 官方客户端主题属性并以真实身份、隔离 realm 和实际浏览器验证。
实际结果与未完成项见 evidence/validation.md。
