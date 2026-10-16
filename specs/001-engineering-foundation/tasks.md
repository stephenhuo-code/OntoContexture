---

description: "Task list for 001 工程基座"
---

# Tasks: 001 工程基座

**Input**: Design documents from `specs/001-engineering-foundation/`

**Prerequisites**: plan.md、spec.md、research.md、data-model.md、contracts/、quickstart.md

**Tests**: 宪法 I 要求测试驱动：每个故事内，测试任务排在实现任务之前，且 MUST 先提交并确认失败，再写实现。

**Organization**: 按 spec 的 4 个用户故事分组。US1 开发者能开工；US2 一键部署与 CI；US3 最小链路跑通；US4 三项选型。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件，且不依赖未完成的任务）
- **[Story]**：所属用户故事（US1–US4）
- 路径均相对仓库根目录；目录约定见 ADR-0009

## 统一约定（各任务引用）

- Keycloak 本地 realm：`contexture`；客户端 `contexture-bff`（机密客户端，开启标准令牌交换）、`contexture-ai-gateway`（作为受众）；
  角色 `admin`（管理员）、`ai-engineer`（AI 工程师）、`business-user`（业务用户）；测试用户 `admin1`、`engineer1`、`user1`。
- 部署常量：`CTX_TENANT_ID=local`。
- 错误码：`auth.invalid_token`（401）、`auth.invalid_audience`（403）、`upstream.unavailable`（502）；格式见
  `contracts/schemas/error.json`（`code` 须匹配 `^[a-z]+(\.[a-z_]+)+$`，必填 `code`、`message`、`trace_id`）。
- 关联属性名见 `contracts/otel/attributes.md`：`ctx.tenant.id`（必填）、`ctx.user.id`、`ctx.agent.id`、`ctx.run.id`、`ctx.session.id`、
  `ctx.token.id`（必填）等；属性名不得自造。
- MCP 示例工具：`list_objects`，参数 `type_key`（string）、`limit`（integer，`≤ 100`，默认 20）；超过行数上限时截断并标记 `truncated`。

---

## Phase 1: Setup（仓库骨架，D1）

**Purpose**: 按 ADR-0009 建立仓库与工作区，所有后续任务都在此基础上进行

- [ ] T001 按 ADR-0009 创建目录骨架并为每个空目录加 `README.md` 说明用途：`apps/web/`、`services/bff/`、`packages/py-core/`、`packages/ts-api/`、`contracts/{openapi,mcp,schemas,otel}/`、`deploy/{components,helm/contexture,kind,offline}/`、`tools/`、`tests/e2e/`、`extensions/`、`third_party/`
- [ ] T002 在 `pyproject.toml` 建立 uv workspace（成员 `packages/py-core`、`services/bff`、`tools`），Python 3.12，配置 ruff、pyright（strict）与 pytest-cov（`fail_under = 80`）
- [ ] T003 [P] 在 `pnpm-workspace.yaml` 与根 `package.json` 建立 pnpm workspace（成员 `apps/web`、`packages/ts-api`），配置 eslint、prettier、TypeScript 5
- [ ] T004 [P] 在 `Makefile` 定义目标 `test`、`lint`、`up`、`down`、`seed`、`e2e`、`components-check`、`offline-package`（暂为占位，后续任务实现）
- [ ] T005 [P] 在 `.pre-commit-config.yaml` 配置 ruff、pyright、eslint，并更新 `.gitignore`（Python、Node、kind、Helm 产物）
- [ ] T006 [P] 将契约落位：`specs/001-engineering-foundation/contracts/openapi/skeleton.yaml` → `contracts/openapi/bff.yaml`；`error.json`、`audit-event.json` → `contracts/schemas/`；`attributes.md` → `contracts/otel/`
- [ ] T007 [P] 在 `contracts/mcp/list_objects.yaml` 编写示例工具契约：工具名 `list_objects`，输入 `type_key`（string，必填）、`limit`（integer，`≤ 100`，默认 20），输出 `columns`（string[]）、`rows`（array）、`truncated`（boolean）
- [ ] T008 [P] 在 `tools/license-allowlist.yaml` 列出允许的许可（Apache-2.0、MIT、BSD-2-Clause、BSD-3-Clause、ISC、PostgreSQL 及同等宽松许可），并列出禁止项（AGPL、SSPL、BUSL）；已批准例外单列（OM 采集框架与内置 MCP 的 CCL，ADR-0011）
- [x] T009 以子仓库方式添加织境维护的 OM 仓库到 `third_party/openmetadata/src/`（`https://github.com/stephenhuo-code/OpenMetadata`，分支 `ctx/2.0.3`，锁定上游 `2.0.3-release` 提交 `b76076bf`，浅克隆），并编写 `third_party/openmetadata/UPSTREAM.yaml` 与空的 `PATCHES.md`

---

## Phase 2: Foundational（阻塞所有故事的前置）

**Purpose**: 组件清单规范、基础 CI、本地集群与 Keycloak realm；完成前任何故事不得开始

- [ ] T010 [P] 在 `deploy/components/component.schema.json` 定义组件清单 JSON Schema：必填 `name`、`version`（必须是确切版本，不得为 `latest` 或范围）、`image`（`source`: `official` | `self-built`，`refs`: string[]）、`license`、`customization`（`config` | `extension` | `patch`）、`upstream`、`owner`、`smoke_test`
- [ ] T011 [P] 在 `tools/tests/test_components_check.py` 编写失败测试：缺少 `component.yaml`、版本为 `latest`、许可不在 `tools/license-allowlist.yaml`、镜像未列入离线清单、缺少冒烟测试，均使检查失败
- [ ] T012 在 `tools/components_check.py` 实现组件检查（遍历 `deploy/components/*/component.yaml`，按 T010 的 Schema 与 T008 的白名单校验），并接入 `make components-check`
- [ ] T013 在 `.github/workflows/ci.yml` 建立基础 CI：ruff、pyright、eslint、`make test`、`make components-check`（扫描与覆盖率门禁在 US2 补齐）
- [ ] T014 [P] 在 `deploy/kind/cluster.yaml` 编写本地集群配置（1 控制面 + 2 工作节点，映射 80 / 443 端口供 Envoy Gateway 使用）
- [ ] T015 在 `deploy/components/keycloak/tests/test_realm.py` 编写失败测试：用 Testcontainers 启动 Keycloak 26.8.0 并导入 realm，`user1` 登录后以 `contexture-bff` 做标准令牌交换（`audience=contexture-ai-gateway`），断言新令牌 `sub` 为 `user1`、`azp` 为 `contexture-bff`、`aud` 含 `contexture-ai-gateway`、`realm_access.roles` 含 `business-user`
- [ ] T016 在 `deploy/components/keycloak/config/realm-contexture.json` 编写 realm 配置（统一约定中的客户端、角色、测试用户；`contexture-bff` 的标准令牌交换开启；受众映射器把 `contexture-ai-gateway` 加入登录令牌的 `aud`），使 T015 通过

**Checkpoint**: 组件清单规范可校验，基础 CI 运行，Keycloak realm 的令牌交换已验证

---

## Phase 3: User Story 1 - 开发者拿到能直接开工的仓库和公共库 (Priority: P1) 🎯 MVP

**Goal**: 交付公共库 `contexture-core` v0.1（D2）与 `bff` 最小版本（D3）；`bff` 不自写任何跨切面代码

**Independent Test**: 参照 `bff` 新增一个接口并跑通测试 ≤ 30 分钟，且没有写令牌验证、追踪或错误处理代码（SC-001）

### Tests for User Story 1（先写并确认失败）⚠️

- [ ] T017 [P] [US1] 在 `packages/py-core/tests/test_config.py` 编写测试：`CTX_TENANT_ID` 缺失时启动失败；配置可从环境变量与挂载文件加载
- [ ] T018 [P] [US1] 在 `packages/py-core/tests/test_errors.py` 编写测试：错误输出符合 `contracts/schemas/error.json`（必填 `code`、`message`、`trace_id`，`code` 匹配 `^[a-z]+(\.[a-z_]+)+$`，不允许额外字段）
- [ ] T019 [P] [US1] 在 `packages/py-core/tests/test_auth.py` 编写测试（用本地生成的 JWKS 签发令牌）：合法令牌构建出请求上下文（`tenant_id` 取自配置、`user_id` = `sub`、`agent_id` = `azp`、`roles`、`token_id` = `jti`）；验签失败或过期 → 401 `auth.invalid_token`；受众不符 → 403 `auth.invalid_audience`
- [ ] T020 [P] [US1] 在 `packages/py-core/tests/test_telemetry.py` 编写测试：一次请求的 span 与结构化日志自动带 `ctx.tenant.id`、`ctx.user.id`、`ctx.agent.id`、`ctx.token.id`；出站 HTTP 携带 W3C `traceparent` 与 Baggage
- [ ] T021 [P] [US1] 在 `packages/py-core/tests/test_mcp.py` 编写测试：令牌交换请求为 `grant_type=urn:ietf:params:oauth:grant-type:token-exchange`、`audience=contexture-ai-gateway`，结果按受众缓存至过期前；用测试内启动的 MCP 服务器（MCP SDK，Streamable HTTP）调用 `list_objects`，断言请求带 Bearer 令牌与 `traceparent`，`limit` 大于 100 时在客户端报错
- [ ] T022 [P] [US1] 在 `packages/py-core/tests/test_ontology.py` 编写测试（模拟 OM REST 接口）：只返回审批状态为已批准的术语与属性，未批准的不返回；结果映射为 `ObjectTypeRef`（`type_uri` 形如 `urn:ctx:type:<领域包>:<类型名>`，`attributes` 含 `name`、`data_type`、`required`、`data_level`）；结果缓存
- [ ] T023 [P] [US1] 在 `services/bff/tests/contract/test_contract.py` 编写 Schemathesis 契约测试，覆盖 `contracts/openapi/bff.yaml` 的全部接口
- [ ] T024 [P] [US1] 在 `services/bff/tests/unit/test_objects.py` 编写测试：`GET /bff/v1/object-types/{typeKey}/objects` 组合 OM 的对象定义与 `list_objects` 的结果，返回 `ObjectListView`（`object_type`、`items`、`trace_id`）；`limit` 取值范围 1–100；OM 或 AI 网关不可用时返回 502 `upstream.unavailable` 并记录追踪
- [ ] T025 [P] [US1] 在 `services/bff/tests/integration/test_auth_flow.py` 编写集成测试（Testcontainers：Keycloak 26.8.0 + Valkey）：`/bff/v1/auth/login` 302 跳转 Keycloak，回调后建立会话，`GET /bff/v1/me` 返回 `tenant_id` 与 `user_id`，`POST /bff/v1/auth/logout` 返回 204 后再访问为 401；浏览器侧只有会话 Cookie

### Implementation for User Story 1

- [ ] T026 [P] [US1] 在 `packages/py-core/src/contexture_core/config.py` 实现配置加载（pydantic-settings），提供 `tenant_id` 常量（T017）
- [ ] T027 [P] [US1] 在 `packages/py-core/src/contexture_core/errors.py` 实现统一错误类型与 FastAPI 异常处理器（T018）
- [ ] T028 [US1] 在 `packages/py-core/src/contexture_core/auth.py` 实现 JWKS 缓存验签与请求上下文构建，以 FastAPI 依赖项提供，统一返回 401 / 403（T019）
- [ ] T029 [US1] 在 `packages/py-core/src/contexture_core/telemetry.py` 实现 OTel 初始化与关联属性注入（FastAPI 与 httpx 插桩、日志关联），属性名严格取自 `contracts/otel/attributes.md`（T020）
- [ ] T030 [US1] 在 `packages/py-core/src/contexture_core/mcp.py` 实现标准令牌交换客户端（按受众缓存）与 MCP 调用封装（MCP SDK Streamable HTTP，透传 `traceparent`）（T021）
- [ ] T031 [US1] 在 `packages/py-core/src/contexture_core/ontology.py` 实现经 OM REST 读取已审批术语与属性并缓存（T022）
- [ ] T032 [US1] 在 `packages/py-core/pyproject.toml` 设定版本 `0.1.0` 与依赖锁定，并在 `packages/py-core/README.md` 说明各模块用法
- [ ] T033 [US1] 在 `services/bff/src/contexture_bff/main.py` 组装应用：只通过公共库获得配置、鉴权、追踪与错误处理
- [ ] T034 [US1] 在 `services/bff/src/contexture_bff/api/auth.py` 实现 `/bff/v1/auth/login`、`/callback`、`/logout`（Authlib OIDC 授权码 + PKCE，会话存 Valkey）（T025）
- [ ] T035 [P] [US1] 在 `services/bff/src/contexture_bff/api/me.py` 实现 `GET /bff/v1/me`（`tenant_id`、`user_id`、`display_name`、`roles`）
- [ ] T036 [P] [US1] 在 `services/bff/src/contexture_bff/adapters/om.py` 与 `adapters/data.py` 分别封装对象定义读取（公共库 `ontology`）与 `list_objects` 调用（公共库 `mcp`）
- [ ] T037 [US1] 在 `services/bff/src/contexture_bff/api/objects.py` 实现 `GET /bff/v1/object-types/{typeKey}/objects`（T023、T024）
- [ ] T038 [P] [US1] 编写 `services/bff/Dockerfile`（非 root、只读文件系统）与 `deploy/helm/contexture/charts/bff/` 子 Chart
- [ ] T039 [US1] 在 `services/bff/README.md` 编写“新增一个接口”的步骤（契约 → 测试 → 实现），并按此实际演练一次、记录用时（SC-001）

**Checkpoint**: 公共库与 `bff` 的单元、契约、集成测试全部通过；覆盖率 ≥ 80%

---

## Phase 4: User Story 2 - 一条命令部署环境，CI 自动把关 (Priority: P1)

**Goal**: 组件部署目录（D5）、本地一键部署（D6）、完整 CI 门禁（D8）、离线安装包（D9）

**Independent Test**: 新机器上 `make up` 拉起全部组件；CI 两个故意失败用例被拦截；离线包在断网 kind 中安装成功（SC-002、SC-004、SC-005）

### Tests for User Story 2（先写并确认失败）⚠️

- [ ] T040 [P] [US2] 在 `tests/e2e/test_up.sh` 编写部署验收脚本：`make up` 后所有组件的 Helm test 通过，Pod 均就绪
- [ ] T041 [P] [US2] 在 `tools/tests/fixtures/` 准备 CI 故意失败用例：一个引入 AGPL 依赖的示例包、一个删除了 `version` 的 `component.yaml`，并在 `tools/tests/test_ci_gates.py` 断言许可检查与组件检查对其失败
- [ ] T042 [P] [US2] 在 `tests/e2e/test_offline_install.sh` 编写离线安装验收：在禁止外网访问的 kind 集群中用离线包安装，全部组件就绪

### Implementation for User Story 2（每个组件：`component.yaml` + Chart 或上游 Chart 引用 + `values/base.yaml` + `values/local.yaml` + `tests/` 冒烟测试）

- [ ] T043 [P] [US2] 组件 Keycloak：`deploy/components/keycloak/`（官方镜像 26.8.0，导入 T016 的 realm）
- [ ] T044 [P] [US2] 组件 PostgreSQL：`deploy/components/postgresql/`（CloudNativePG，为 openmetadata、langfuse、airflow、keycloak 各建一个 database）
- [ ] T045 [P] [US2] OM 镜像构建：`third_party/openmetadata/build/`（Dockerfile 与构建脚本，从子仓库 `third_party/openmetadata/src/` 构建 `openmetadata-server` 与 `openmetadata-ingestion`，镜像版本 `2.0.3-ctx.0`）
- [ ] T046 [US2] 组件 OpenMetadata：`deploy/components/openmetadata/`（自建镜像，开启 RDF 指向 Fuseki，身份接本地 Keycloak 自定义 OIDC，`config/` 中初始化共用字段与 `hasProperty` 关系类型）
- [ ] T047 [P] [US2] 组件 Jena Fuseki：`deploy/components/fuseki/`
- [ ] T048 [P] [US2] 组件 OpenSearch：`deploy/components/opensearch/`
- [ ] T049 [P] [US2] 组件 Doris：`deploy/components/doris/`（Doris Operator；`config/` 中建本体实例库 database 与只读账号 `ctx_reader`，按负载类型划分 workload group）
- [ ] T050 [P] [US2] 组件 MCP Toolbox：`deploy/components/mcp-toolbox/`（官方镜像，织境自写 Chart；数据源指向 Doris，凭证来自 K8s Secret）
- [ ] T051 [P] [US2] 组件 OTel Collector：`deploy/components/otel-collector/`（网关模式，开启持久化队列，导出到 Langfuse 与可观测后端）
- [ ] T052 [P] [US2] 组件 Langfuse：`deploy/components/langfuse/`（官方 Chart，ClickHouse、Valkey、对象存储用 SeaweedFS）
- [ ] T053 [P] [US2] 组件 Airflow：`deploy/components/airflow/`（官方 Chart，KubernetesExecutor；001 只验证就绪）
- [ ] T054 [P] [US2] 组件 Envoy Gateway：`deploy/components/envoy-gateway/`（Gateway API 路由：页面 → `web`，`/bff/*` → `bff`，MCP 与模型 → AI 网关）
- [ ] T055 [US2] 伞形 Chart：`deploy/helm/contexture/Chart.yaml` 与 `values-local.yaml` 汇总全部组件与 `bff`、`web`，并提供精简配置 `values-lite.yaml`（降低副本与资源）
- [ ] T056 [US2] 在 `tools/up.sh` 实现 `make up` / `make down`：创建 kind 集群、安装伞形 Chart、等待就绪并运行冒烟测试（T040）
- [ ] T057 [US2] 补齐 `.github/workflows/ci.yml`：覆盖率门禁 ≥ 80%、oasdiff（对比主分支 `contracts/openapi/`）、Syft 生成 SBOM、Grype 与 Trivy 漏洞扫描、按 `tools/license-allowlist.yaml` 的许可检查（T041）
- [ ] T058 [US2] 在 `tools/offline_package.py` 实现离线打包：从全部 `component.yaml` 汇总镜像清单、导出镜像与 Chart 到 `deploy/offline/dist/`，并编写 `deploy/offline/install.sh`（T042）

**Checkpoint**: `make up` 在本地就绪；CI 门禁完整；离线包可在断网 kind 中安装

---

## Phase 5: User Story 3 - 最小链路真实跑通 (Priority: P1)

**Goal**: 织境 Web 最小外壳（D4）、Toolbox 示例工具与 AI 网关配置、示例数据，完成“最终演示”6 步

**Independent Test**: 按 quickstart 第 3 节在本地执行 6 步，全部通过（SC-003）

**Depends on**: US1、US2，以及 US4 的 T073–T076（AI 网关选定、Toolbox 连 Doris 的结论）

### Tests for User Story 3（先写并确认失败）⚠️

- [ ] T059 [P] [US3] 在 `deploy/components/mcp-toolbox/tests/test_list_objects.py` 编写测试（Testcontainers 启动 Doris）：`list_objects(type_key="equipment", limit=20)` 只返回本体实例库中 `equipment` 表的行；`limit` 超过 100 被拒绝；使用只读账号执行写语句失败
- [ ] T060 [P] [US3] 在 `deploy/components/ai-gateway/tests/test_policies.py` 编写网关策略测试：无令牌或受众不是 `contexture-ai-gateway` 的请求被拒绝；合法令牌可调用 `list_objects`；审计记录含 `sub`、`azp`、工具名、查询摘要、`trace_id`
- [ ] T061 [P] [US3] 在 `apps/web/src/__tests__/objects-page.test.tsx` 编写 Vitest 组件测试：示例页面渲染对象定义表与设备列表，接口错误时显示统一错误信息
- [ ] T062 [P] [US3] 在 `tests/e2e/demo.spec.ts` 编写 Playwright 端到端测试，覆盖最终演示第 1–2 步（登录、看到“设备”定义与列表）与第 5 步（无令牌或受众不符直接调 `bff` 返回 401 / 403）
- [ ] T063 [P] [US3] 在 `tests/e2e/test_trace_and_audit.py` 编写测试，覆盖最终演示第 3–4 步：按本次 `trace_id` 查到 web → bff → AI 网关 → MCP Toolbox → Doris 与 bff → OM 的全部 span，每个 span 的 `ctx.tenant.id` 相同；AI 网关审计含人（`sub`）、调用方（`azp` = `contexture-bff`）、工具名、查询摘要、返回行数

### Implementation for User Story 3

- [ ] T064 [US3] 在 `deploy/components/mcp-toolbox/config/tools.yaml` 定义 `list_objects` 参数化查询工具，与 `contracts/mcp/list_objects.yaml` 一致（T059）
- [ ] T065 [US3] 在 `deploy/components/ai-gateway/config/` 编写路由、令牌校验（Keycloak JWKS，受众 `contexture-ai-gateway`）、按角色的工具授权规则（`admin`、`ai-engineer`、`business-user` 均可调用 `list_objects`）与审计输出配置（T060）
- [ ] T066 [US3] 在 `tools/seed.py` 实现 `make seed`：在 OM 创建并审批“设备”对象（术语）及其属性，在 Doris 本体实例库建 `equipment` 表并写入 10 行示例数据（`object_uri` 形如 `urn:ctx:obj:local:Equipment:<编号>`）
- [ ] T067 [P] [US3] 在 `packages/ts-api/` 由 `contracts/openapi/bff.yaml` 生成前端 API 客户端，并加入构建脚本
- [ ] T068 [US3] 在 `apps/web/` 搭建 React + Vite 工程：登录跳转（调用 `/bff/v1/auth/login`）、退出、示例页面 `/objects/equipment`（T061）
- [ ] T069 [P] [US3] 编写 `apps/web/Dockerfile`（构建产物交由 nginx 提供）与 `deploy/components/web/`（`component.yaml`、Chart、冒烟测试）
- [ ] T070 [US3] 在 `Makefile` 实现 `make e2e`，运行 T062、T063；在本地执行 quickstart 第 3 节 6 步并记录结果

**Checkpoint**: 最终演示 6 步在本地全部通过

---

## Phase 6: User Story 4 - 三项选型有结论 (Priority: P2)

**Goal**: 选定 AI 网关、确认 Toolbox 能否连 Doris、选定系统可观测后端（D10）

**Independent Test**: ADR-0013 与架构文档写入三项结论与验证记录（SC-006）

**Note**: T071–T076 应在第 1 周执行（US3 依赖其结论）

- [ ] T071 [P] [US4] 在 `docs/research/ai-gateway-spike/agentgateway/` 部署 agentgateway 候选配置（本地 kind），接入 Keycloak 令牌校验、MCP Toolbox 与一个模型服务（key 由负责人配置，OpenAI 兼容地址）
- [ ] T072 [P] [US4] 在 `docs/research/ai-gateway-spike/agent-router/` 部署 Agent Router 候选配置，接入同样的令牌校验、MCP Toolbox 与模型服务
- [ ] T073 [US4] 按 ADR-0013 的 4 项验证两个候选：① 经网关调用 Toolbox；② 审计能否记录 `sub`、`azp`、工具与查询内容；③ 作为模型网关供 OpenAI 兼容客户端调用；④ 令牌受众校验；并核实开源版是否具备按令牌声明的 token 配额、按模型授权与虚拟 key。结果记入 `docs/research/ai-gateway-spike/README.md`
- [ ] T074 [US4] 用 Toolbox 的 mysql 数据源连接 Doris 执行 `list_objects`，记录结论（可用，或改用 Apache Doris MCP Server）到 `docs/research/ai-gateway-spike/README.md`
- [ ] T075 [US4] 根据 T073、T074 的结论更新 `docs/adr/0013-数据访问与AI网关.md`（选定的网关、Toolbox 的 Doris 数据源方式，删去已完成的 spike 项）
- [ ] T076 [US4] 为选定的网关创建 `deploy/components/ai-gateway/`（`component.yaml`、Chart、`values/`、冒烟测试），并删除 `docs/research/ai-gateway-spike/` 中未选中的配置
- [ ] T077 [P] [US4] 创建可观测后端组件：`deploy/components/prometheus/`、`deploy/components/jaeger/`、`deploy/components/opensearch-dashboards/`（候选方案），OTel Collector 导出指标与追踪，服务日志进入 OpenSearch
- [ ] T078 [US4] 验证服务指标、日志与追踪可查后，在 `docs/architecture/platform-architecture.md` 第 8 节写入可观测后端结论，并从待决事项中移除

**Checkpoint**: 三项选型均有结论并写入文档

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T079 [P] 在根 `README.md` 编写快速开始：环境要求（建议 16 核 / 64 GB，或使用 `values-lite.yaml`）、`make up`、`make seed`、`make e2e`
- [ ] T080 [P] 按 quickstart 第 1、2、4 节逐项验收，并在 `specs/001-engineering-foundation/quickstart.md` 中修正与实际不符的命令
- [ ] T081 记录 D1–D11 各交付物的实际用时，汇总后更新 `docs/Phase1-特性列表与开发计划.md` 第 3 节的估算（D11）
- [ ] T082 复核宪法检查：组件许可清单（`deploy/components/*/component.yaml`）与架构文档第 4 节的第三方组件表一致；更新 `docs/architecture/platform-architecture.md` 中与实际部署不符之处

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup（Phase 1）**：无依赖（T009 已完成）
- **Foundational（Phase 2）**：依赖 Setup；阻塞全部用户故事
- **US1（Phase 3）**：依赖 Foundational
- **US2（Phase 4）**：依赖 Foundational；T045、T046 依赖 T009
- **US4（Phase 6）**：T071–T074 依赖 US2 的 T043、T049、T050（Keycloak、Doris、Toolbox 已部署）；**应在第 1 周优先执行**
- **US3（Phase 5）**：依赖 US1、US2，以及 US4 的 T073–T076
- **Polish（Phase 7）**：依赖全部故事

### User Story Dependencies

- US1 与 US2 可并行
- US4 的网关与 Toolbox 验证（T071–T076）在 US2 的基础组件就绪后立即开始
- US3 最后汇合，完成最终演示

### Within Each User Story

- 测试先写、先提交、确认失败，再实现（宪法 I）
- 公共库模块先于 `bff`；组件目录先于伞形 Chart；网关选定先于网关配置

### Parallel Opportunities

- Setup：T003–T008 可并行
- Foundational：T010、T011、T014 可并行
- US1：测试 T017–T025 可并行；实现 T026、T027、T035、T036、T038 可并行
- US2：组件目录 T043–T054 中除 T046（依赖 T045）外均可并行
- US3：测试 T059–T063 可并行
- US4：T071 与 T072 并行

---

## Parallel Example: User Story 2

```bash
# 组件目录可同时由多人完成：
Task: "组件 PostgreSQL：deploy/components/postgresql/"
Task: "组件 Doris：deploy/components/doris/"
Task: "组件 MCP Toolbox：deploy/components/mcp-toolbox/"
Task: "组件 Langfuse：deploy/components/langfuse/"
```

---

## Implementation Strategy

### MVP First（US1）

1. 完成 Setup 与 Foundational
2. 完成 US1：公共库与 `bff` 的全部测试通过
3. **停下验证**：参照 `bff` 新增一个接口，用时 ≤ 30 分钟

### Incremental Delivery（对应 plan 的两周安排）

- **第 1 周**：Setup → Foundational → US1 公共库；US2 的 Keycloak、PostgreSQL、OM、Doris、Toolbox；US4 的网关与 Toolbox 验证
- **第 2 周**：US1 `bff`；US2 其余组件、伞形 Chart、CI 门禁、离线包；US3 最小链路与最终演示；US4 可观测后端；Polish

### Parallel Team Strategy（2–3 人）

- 开发者 A：US1（公共库、`bff`）→ US3 的 `web`
- 开发者 B：US2（组件目录、伞形 Chart、离线包）→ US3 的 Toolbox、网关配置与示例数据
- 开发者 C（或 B 兼任）：US4（网关与 Toolbox 验证、可观测后端）→ CI 门禁

---

## Notes

- [P] = 不同文件、无未完成依赖
- 每个任务完成后提交；测试提交须早于对应实现提交（PR 评审核对）
- 任何组件版本不得写 `latest`；镜像必须进入离线清单
- 阿里云测试环境不在 001（见开发计划 004）
