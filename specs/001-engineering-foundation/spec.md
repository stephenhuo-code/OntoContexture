# Feature Specification: 001 工程基座

**Feature Branch**: `001-engineering-foundation`

**Created**: 2026-10-04（2026-10-16 按“交付物 + 演示”重写）

**Status**: Draft

**Input**: User description: "001 工程基座与交付流水线"

## 一句话

001 做完后，团队拿到一个**能直接开始写业务功能的仓库和环境**：目录与公共库就位，所有开源组件一条命令部署到本地环境，CI 自动
检查，并且一条“登录 → 查数据 → 看到结果”的最小链路已经真实跑通。001 本身不交付任何业务功能。

## 已完成的部分（文档）

| 交付物 | 位置 |
| --- | --- |
| 平台技术架构 | `docs/architecture/platform-architecture.md`、`docs/images/平台服务架构.svg` |
| 架构决策 | `docs/adr/0001`–`0013`（0001–0013 均已接受） |
| 仓库结构与代码架构 | `docs/adr/0009-仓库结构与代码架构.md` |
| Phase 1 特性与排期 | `docs/Phase1-特性列表与开发计划.md` |

001 剩下的工作是**把这些设计落成可运行的东西**，见下文。

## Clarifications

### Session 2026-10-04

- Q: Phase 1 的自建服务应该按什么粒度拆分？ → A: 由 plan 阶段给出完整架构设计，以“按能力域拆分、一个服务可承载多个特性”为原则（已落实为 ADR-0012、0013：Phase 1 自建后端只有 `bff`）。

### Session 2026-10-08

- Q: Phase 1 是否按多租户设计？ → A: 不。单租户；审计、追踪、日志保留 `tenant_id` 常量（宪法 v1.5.0，ADR-0007）。
- Q: 是否需要服务模板？ → A: 不做。`bff` 即参考实现；开源组件按“每个组件一个标准目录 + 清单 + CI 检查”管理（ADR-0009）。

### Session 2026-10-16

- Q: 001 的 spec 应该写到什么程度？ → A: 写清楚交付物（是什么、放在哪、怎么验）和最终演示，读完就知道要做什么。
- Q: 身份服务用哪个 Keycloak？ → A: 不另行部署，使用负责人现有的 Keycloak（26.8.0），本机与 Paperclip 共用同一个 realm（本机即测试环境）。织境的客户端、角色与受众映射以增量方式导入，不覆盖已有配置。自动化测试用 Testcontainers 临时 Keycloak。
- Q: 没有 Keycloak 的客户怎么办？ → A: 部署包内置 Keycloak，开关 `keycloak.enabled` 默认关闭：有 Keycloak（≥ 26.2）的客户接入其现有实例；没有的客户打开开关，随织境部署 Keycloak，并可把客户已有的 AD / LDAP / 飞书 / 企业 OIDC 接到这个 Keycloak 上。
- Q: 阿里云测试环境何时搭建？ → A: 放到 004 之后，先在本地把界面与最小链路调通。

## 交付清单

| # | 交付物 | 具体内容 | 放在哪 | 怎么验 |
| --- | --- | --- | --- | --- |
| D1 | 仓库骨架 | 按 ADR-0009 建好目录与 Python / 前端工作区；`Makefile` 提供常用命令 | 仓库根目录 | `make test` 在空骨架上通过 |
| D2 | 公共库 `contexture-core` v0.1 | `auth`：验 Keycloak 令牌，取出人、Agent、角色、`tenant_id`；`mcp`：标准令牌交换后经 AI 网关调用 MCP 工具；`telemetry`：日志与追踪自动带关联属性；`ontology`：从 OM 读取已审批的对象定义；`errors`：统一错误格式；`config`：配置与 `tenant_id` 常量 | `packages/py-core/` | 每个模块有单元测试；覆盖率 ≥ 80% |
| D3 | `bff` 最小版本 | 两个接口：`GET /bff/v1/me`（当前用户）、`GET /bff/v1/object-types/{typeKey}/objects`（对象定义 + 实例列表）；只用公共库，不自写令牌验证、追踪、错误处理 | `services/bff/` | 单元、契约、集成测试通过 |
| D4 | 织境 Web 最小外壳 | Keycloak 登录 / 退出；一个示例页面：显示“设备”对象的属性定义和设备列表；打包为 nginx 静态镜像 | `apps/web/` | 浏览器能登录并看到示例页面 |
| D5 | 组件部署目录 | 每个组件一个标准目录（清单、Chart、参数、配置、冒烟测试）：Keycloak（开关 `keycloak.enabled` 默认关闭，关闭时接入外部 Keycloak，两种模式都用增量导入写入织境配置）、OpenMetadata（自建镜像，开启 RDF）、Fuseki、PostgreSQL、OpenSearch、Doris、AI 网关、MCP Toolbox、OTel Collector、Langfuse、Airflow、nginx（web） | `deploy/components/<组件>/` | 每个组件冒烟测试通过；CI 清单检查通过；Keycloak 两种模式各部署验证一次 |
| D6 | 一键部署（本地） | 一条命令在本地 kind 部署全部组件与 `bff`、`web` | `deploy/helmfile.yaml.gotmpl`、`Makefile` | `make up` 后所有组件就绪 |
| D8 | CI 门禁 | 每次提交：构建、单元 / 契约 / 集成测试、覆盖率 ≥ 80%、静态检查、SBOM、许可与漏洞扫描、组件清单检查 | `.github/workflows/` | 故意引入 AGPL 依赖或删掉组件版本号，CI 失败 |
| D9 | 离线安装包 | 打包镜像与 Chart（x86_64），可在断网环境安装 | `deploy/offline/` | 在断网的 kind 集群安装成功 |
| D10 | 三项选型结论 | ① AI 网关：agentgateway 还是 Agent Router（ADR-0013 的 4 项验证）；② MCP Toolbox 能否直接连 Doris；③ 系统可观测后端（服务指标与日志） | 更新 ADR-0013 与架构文档 | 每项有结论与验证记录 |
| D11 | 实际用时记录 | 记录 001 各交付物的实际用时，对比估算 | 开发计划第 3 节 | 用于校准后续排期 |
| D12 | 手动验收文档 | 按宪法 v1.6.0：前置条件、逐步操作、预期结果、对应的用户故事与成功标准、验收记录；产品负责人不读代码即可执行 | `specs/001-engineering-foundation/acceptance.md` | 产品负责人按文档手动验收通过 |

## 最终演示（001 的验收）

在本地环境演示（阿里云测试环境在 004 之后搭建，届时复演一遍）：

1. 用测试用户在浏览器登录织境 Web（跳转 Keycloak）。
2. 打开示例页面，看到“设备”对象的属性定义（来自 OM，已审批）和设备列表（来自 Doris）。
3. 打开追踪界面，按本次请求的 `trace_id` 看到完整链路：web → bff → AI 网关 → MCP Toolbox → Doris，以及 bff → OM，每一跳都带
   相同的 `tenant_id`。
4. 查看 AI 网关的审计记录：能看到人（`sub`）、调用方（`azp` = bff）、工具名、查询摘要、返回行数。
5. 用一个没有登录的请求、或受众不对的令牌直接调 `bff`：返回 401 / 403，错误格式统一。
6. 让 CI 跑一次：故意加一个 AGPL 依赖，CI 失败；删掉后通过。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 开发者拿到能直接开工的仓库和公共库 (Priority: P1)

后续特性的开发者克隆仓库后，按目录约定新增代码，跨切面能力（令牌、追踪、错误格式、取数）直接调用公共库，不用自己写。

**Independent Test**: 参照 `bff` 新增一个接口并跑通测试，用时不超过 30 分钟，且没有写任何令牌验证、追踪或错误处理代码。

**Acceptance Scenarios**:

1. **Given** 仓库骨架与公共库（D1、D2），**When** 开发者参照 `bff` 新增一个接口，**Then** 30 分钟内测试通过。
2. **Given** `bff`，**When** 收到无效或受众不符的令牌，**Then** 公共库直接拒绝并返回统一错误。
3. **Given** `bff` 处理一次请求，**When** 查看日志与追踪，**Then** 自动带有 `tenant_id`、人、调用方等属性。

---

### User Story 2 - 一条命令部署环境，CI 自动把关 (Priority: P1)

开发者在本地一条命令拉起全部组件；不合规的依赖或组件配置在 CI 被拦下；交付时能打出离线包。

**Independent Test**: 在一台新机器上 `make up` 拉起本地环境；在 CI 中验证 D8 的两个故意失败用例；在断网 kind 中安装离线包。

**Acceptance Scenarios**:

1. **Given** 新机器，**When** 执行一键部署（D6），**Then** 全部组件就绪且冒烟测试通过。
2. **Given** 引入 AGPL 依赖或删掉组件版本号，**When** CI 运行，**Then** 构建失败。
3. **Given** 离线安装包（D9），**When** 在断网 kind 中安装，**Then** 安装成功。

---

### User Story 3 - 最小链路真实跑通 (Priority: P1)

架构负责人看到“登录 → 查数据 → 看到结果”在真实组件上跑通，并能查到完整追踪与审计，证明架构可行。

**Independent Test**: 按“最终演示”的 6 步在本地环境执行一遍。

**Acceptance Scenarios**:

1. **Given** 已部署的环境，**When** 测试用户打开示例页面，**Then** 看到来自 OM 的对象定义与来自 Doris 的数据。
2. **Given** 同一次请求，**When** 查看追踪，**Then** 一条追踪覆盖全部跳数，每跳 `tenant_id` 相同。
3. **Given** 同一次请求，**When** 查看 AI 网关审计，**Then** 能看到人、调用方、工具、查询摘要与返回行数。

---

### User Story 4 - 三项选型有结论 (Priority: P2)

AI 网关、Toolbox 连 Doris、可观测后端三项在 001 期间验证并定下，后续特性不再悬而未决。

**Independent Test**: 检查 ADR-0013 与架构文档已写入三项结论及验证记录。

**Acceptance Scenarios**:

1. **Given** ADR-0013 的 4 项验证，**When** 001 完成，**Then** 选定 agentgateway 或 Agent Router 并写明理由。
2. **Given** Toolbox 的 mysql 数据源，**When** 连接 Doris 执行示例查询，**Then** 得出“可用 / 改用 Doris MCP Server”的结论。
3. **Given** 可观测后端候选，**When** 001 完成，**Then** 选定并部署，服务指标与日志可查。

### Edge Cases

- OM 或 Doris 不可用：`bff` 返回明确错误并记录追踪，不吞掉错误。
- 令牌过期或受众不符：公共库统一返回 401 / 403。
- 组件升级导致冒烟测试失败：CI 阻止合并。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: MUST 交付 D1–D6、D8–D12 全部交付物，放在表中所列位置（D7 阿里云测试环境移到 004 之后）。
- **FR-002**: 公共库 MUST 覆盖令牌验证（人、Agent、角色、`tenant_id`）、标准令牌交换与 MCP 调用、追踪属性、本体读取、错误格式、配置。
- **FR-003**: `bff` MUST 只通过公共库获得跨切面能力，不自写令牌验证、令牌交换、追踪与错误处理。
- **FR-004**: 取数 MUST 经 AI 网关与 MCP Toolbox，使用数据库只读账号，设置超时与返回行数上限；`bff` 不持有数据库账号。
- **FR-005**: AI 网关 MUST 记录每次调用的审计（人、调用方、工具、查询摘要、返回行数、`trace_id`）。
- **FR-006**: 每个开源组件 MUST 有标准目录与清单，CI MUST 检查版本锁定、许可白名单、离线镜像清单与冒烟测试。
- **FR-007**: 本地环境 MUST 用一套部署编排（helmfile）部署，并可直接用于后续的阿里云测试环境；Keycloak MUST 支持两种模式（接入外部 Keycloak、随织境部署），默认接入外部；001 本机接入负责人现有的 Keycloak。
- **FR-008**: 单租户部署，审计、追踪与日志写入部署常量 `tenant_id`。
- **FR-009**: 三项选型结论（D10）MUST 写入 ADR-0013 与架构文档。

### Key Entities

- **公共库**：所有自建代码共用的跨切面能力，有版本，升级须在最小链路上回归通过。
- **组件清单**（`component.yaml`）：每个开源组件的版本、镜像来源、许可、定制级别与负责人。
- **最小链路**：web → bff → AI 网关 → MCP Toolbox → Doris，以及 bff → OM。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 新开发者参照 `bff` 新增一个接口并跑通测试 ≤ 30 分钟。
- **SC-002**: 新机器上一键部署本地环境 ≤ 30 分钟（不含镜像下载）。
- **SC-003**: “最终演示”6 步在本地环境 100% 通过。
- **SC-004**: CI 的两个故意失败用例（AGPL 依赖、组件版本缺失）100% 被拦截。
- **SC-005**: 离线安装包在断网 kind 中安装成功。
- **SC-006**: 三项选型 100% 有结论并写入文档。

## 不在 001 范围

- 任何业务功能（身份细节、数据访问、指标、本体等由 002 起各特性完成）。
- 数据层授权、多租户、服务模板、对接客户 IdP。
- Omnigent 与 Paperclip 的接入（分别在 014、011）。
- 阿里云测试环境（004 之后）。

## Assumptions

- 设计依据见“已完成的部分”中的架构文档与 ADR-0001–0013。
- 自建服务用 Python（FastAPI），前端技术栈按 ADR-0003。
- 最小链路用少量手工测试数据；模拟工厂数据由 003 提供。
- 织境维护的 OM 仓库已就绪（`stephenhuo-code/OpenMetadata`，分支 `ctx/2.0.3`）。模型服务 key 由负责人在验证 AI 网关的模型网关功能时自行配置。
- 离线安装包只支持 x86_64。
