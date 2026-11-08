---

description: "005 源系统元数据采集 · 任务清单"
---

# Tasks: 源系统元数据采集（Source Metadata Ingestion）

**Input**: `specs/005-source-metadata-ingestion/` 下的 plan.md、spec.md、research.md、data-model.md、contracts/openapi.yaml、quickstart.md

**Prerequisites**: plan.md、spec.md（必需）；research.md、data-model.md、contracts/、quickstart.md

**Tests**: 宪法 I 要求测试先行，测试任务为必选。每个测试任务 MUST 先提交并确认失败，再做对应实现；集成测试使用真实依赖（`-m cluster`）。
断言基于 003 金标准（MES 13 张表 / 79 字段、QMS 7 / 53、Doris 8 / 66，合计 28 / 198）与 viewlab 标准答案，**不得断言原型中的示例数值**（宪法 v2.2.0）。

**通用约束（每个任务都适用）**:

- BFF 只调用 OpenMetadata 公开 API（research R7），以登录用户的委托令牌（受众 `contexture-openmetadata`）调用；不连源库、不调 Airflow、不写 `PipelineStatus`。
- 生产代码中不得出现示例数据源、示例表结构、示例运行记录或“失败时回退示例数据 / 伪造成功”的分支；无数据显示空状态，出错显示真实错误（`upstream.unavailable` 等）。
- 所有写接口校验 `admin` / `ai-engineer` 角色，并记录含 `trace_id`、`tenant_id`、`user_id` 的审计日志（FR-010）。
- 响应中的密码字段恒为 `*********`。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1–US5）

## Path Conventions

monorepo：`apps/web/`、`services/bff/`、`packages/ts-api/`、`contracts/`、`deploy/`、`testdata/`、`tools/`、`tests/e2e/`、`third_party/openmetadata/build/`。

---

## Phase 1: Setup（契约与共享入口）

**Purpose**: 契约先行，生成前端类型

- [X] T001 将 `specs/005-source-metadata-ingestion/contracts/openapi.yaml` 的 10 个路径与全部 schema 合入 `contracts/openapi/bff.yaml`（`info.version` 升为 0.2.0；`$ref` 改为 `../schemas/error.json`；错误码 `source.name_conflict`、`source.deploy_failed`、`source.pipeline_in_flight`、`source.schedule_not_set`、`source.immutable_field`、`upstream.unavailable` 写入描述）
- [X] T002 由 `contracts/openapi/bff.yaml` 重新生成 `packages/ts-api/src/`（沿用该包现有生成命令），并确认 `pnpm --filter @contexture/web build` 通过
- [X] T003 [P] 确认审计事件沿用 `contracts/schemas/audit-event.json` 现有结构，不改 schema：005 的写操作一律记 `action=write`、`resource.kind=api`、`resource.ref=<HTTP 方法> <实际请求路径>`（如 `POST /bff/v1/sources/mock-mes/pipelines/metadata/trigger`，路径即包含目标；schema 无其他可放目标的字段且 `additionalProperties=false`）；在 `services/bff/tests/contract/test_audit_contract.py` 增加契约测试，校验 005 审计事件符合该 schema

---

## Phase 2: Foundational（阶段 A 基础设施 + 阶段 B 测试数据 + 公共骨架）

**Purpose**: 所有用户故事的前置条件。**闸门：T020 未通过不得开始 Phase 3 及以后。** 若 R1 链路不可行，停止并回到负责人决策（ADR-0006 备选），不得自行改路线。

### 阶段 A · 基础设施测试（先写、先失败）

- [X] T004 [P] 在 `deploy/components/keycloak/tests/test_realm.py` 增加测试：`contexture-bff` 登录令牌可交换为受众 `contexture-openmetadata` 的令牌；`contexture-bff` 可用 client credentials 取得服务账号 `service-account-contexture-bff` 的令牌（research R13）
- [X] T005 [P] 在 `deploy/components/airflow/tests/smoke.sh` 增加检查：Airflow 镜像为织境采集镜像、`/pluginsv2` 健康接口可用、dags 卷已挂载且 `DAG_GENERATED_CONFIGS` 位于同一卷、不存在 `contexture_om_dags.py` 及其 DAG
- [X] T006 [P] 在 `deploy/components/openmetadata/tests/smoke.sh` 增加检查：OM 的 pipeline service client 已启用并能连通 Airflow（OM 服务状态接口返回 Airflow 版本 3.3.2）

### 阶段 A · 基础设施实现

- [X] T007 新增 `third_party/openmetadata/build/Dockerfile.airflow`（`FROM apache/airflow:3.3.2-python3.12`，参照上游 `ingestion/Dockerfile.ci` 从子仓库源码安装 `openmetadata-managed-apis` 与 `openmetadata-ingestion[mysql,postgres,oracle,mssql,doris]`，不复制上游示例 DAG），并在 `third_party/openmetadata/build/build.sh` 增加 `airflow` 目标产出 `contexture/openmetadata-ingestion-airflow:<image_version>`；更新 `third_party/openmetadata/build/README.md`
- [X] T008 修改 `deploy/components/keycloak/config/contexture.yaml`：`contexture-bff` 客户端增加 `contexture-openmetadata` 受众 mapper，并开启服务账号（BFF 在 OM 中建档用户的身份，research R13）（使 T004 通过）
- [X] T009 修改 `deploy/components/airflow/values/base.yaml`：镜像改为 T007 产物；SimpleAuthManager 为 OM 配置用户（密码取 `om-secrets/airflow-password`）；`AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session`、启用 CSRF；`dags.persistence` 挂 PVC，`DAG_GENERATED_CONFIGS` 指向该卷子目录；KubernetesExecutor 任务 Pod 使用同一镜像与同一卷（research R2–R4）
- [X] T010 修改 `deploy/components/airflow/values/local.yaml` 与 `deploy/components/airflow/values/lite.yaml`：Airflow 各组件与任务 Pod 模板固定到同一节点（kind 的 `rancher.io/local-path` 只支持 RWO）；在 `deploy/components/airflow/values/base.yaml` 注释中写明 ACK 使用 NAS（RWX）且不固定节点
- [X] T011 修改 `deploy/components/openmetadata/values/base.yaml`：`pipelineServiceClientConfig.enabled: true`、`type: airflow`、`airflow.apiEndpoint: http://airflow-api-server:8080`、`metadataApiEndpoint: http://openmetadata:8585/api`、Airflow 用户 `openmetadata` 与 `om-secrets/airflow-password`；删除“OM 不接 Airflow 编排”的注释（使 T006 通过）
- [X] T012 修改 `tools/up.sh`：构建并 `kind load` 织境 Airflow 镜像（与 OM server 镜像同处）；将该镜像纳入 `tools/offline_package.py` 清单与 `deploy/components/airflow/component.yaml`
- [X] T013 起草 OM 权限清单：在 `specs/005-source-metadata-ingestion/research.md` 新增 R12，列出团队 `admin`、`ai-engineer` 及其 OM 角色 / 策略所授予的具体操作（DatabaseService、IngestionPipeline 的创建 / 编辑 / 部署 / 触发 / 启停，Workflow 测试连接，Database / DatabaseSchema / Table 治理属性编辑，治理选项读取）。**交负责人确认后**才可进行 T014
- [X] T014 在 `tools/om_config.py` 幂等创建 R12 的团队、角色与策略，以及 R13 的 OM 用户 `service-account-contexture-bff` 与角色 `ContextureUserProvisioner`（`user`：Create / ViewAll；`team`：ViewAll / EditUsers），重复执行无副作用；先在 `tools/tests/test_om_config.py` 增加对应测试（先写、先失败）
- [X] T015 更新 `docs/adr/0006-三域数据治理与管线编排.md`（待定问题 2：OM 2.0.3 支持 Airflow 3 外部编排，已采用）与 `docs/adr/0011-OpenMetadata的构建与部署.md`（镜像表新增织境 Airflow 采集镜像及用途）

### 阶段 B · 测试数据（先写测试）

- [X] T016 [P] 新增 `testdata/tests/cluster/test_readonly_accounts.py`：MES（MySQL）与 QMS（PostgreSQL）只读元数据账号能列出库 / 表 / 字段，不能执行任何写操作；003 原有表与数据不变
- [X] T017 [P] 新增 `testdata/tests/cluster/test_viewlab.py`：mock-mes 实例的 `viewlab` 库与 mock-qms 实例的 `viewlab` 库存在；可读账号能读取视图定义；MySQL 受限账号（无 `SHOW VIEW`）读不到视图定义；视图与基表的表级 / 字段级关系与标准答案文件一致
- [X] T018 实现只读账号与 viewlab：`testdata/deploy/secrets.sh` 生成新账号密码；`testdata/mockfactory/load/mysql.py`、`testdata/mockfactory/load/postgres.py` 创建账号与 `viewlab` 库（基表、视图、受限账号）；标准答案写入 `testdata/mockfactory/viewlab.py`（视图 → 上游表及 `columnsLineage`）；`make mock-data` 执行后 T016、T017 通过；修改 `tools/ports.sh`，在现有输出中增加 MES / QMS 只读元数据账号与 viewlab 可读账号、受限账号的用户名及取密码命令（与现有 root 密码输出方式一致）；更新 `testdata/README.md`
- [X] T019 核对 OM Postgres 连接器读取视图定义所用查询（`third_party/openmetadata/src/ingestion/src/metadata/ingestion/source/database/postgres/`），判断 PostgreSQL 受限账号能否复现“视图定义不可读”，结论写入 `specs/005-source-metadata-ingestion/research.md` R10；不能复现时该场景只用 MySQL 验收

### 阶段 A 闸门 · 真实链路验证

- [X] T020 新增 `tests/e2e/test_om_ingestion_chain.py`（`pytest -m cluster`）并跑通：以 `service-account-contexture-bff` 为 `admin1`、`engineer1` 在 OM 建档并同步团队（R13）后，用 `admin1` 的委托令牌（受众 `contexture-openmetadata`）对 MES 只读账号发起 OM 测试连接并读到逐步结果；创建 `DatabaseService` 与 metadata 管道；deploy → trigger → 轮询 `pipelineStatus` 至终态；读取 `logs/{id}/last`；以用户令牌读取服务时密码为 `*********`；`engineer1` 的权限符合 T013；测试结束删除所建实体。把 research R5 验证项 2、3（掩码密码更新保留原值、已有服务掩码密码测试连接）的结论写入 `specs/005-source-metadata-ingestion/research.md`；核对 MySQL / Doris `sslConfig`、PostgreSQL `sslMode`、SQL Server `encrypt` 的具体取值，结论写入 research R9。**本任务通过前不得开始 Phase 3**

### 公共骨架（闸门通过后）

- [X] T021 [P] 在 `services/bff/tests/unit/test_om_client.py` 先写测试：令牌交换受众为 `contexture-openmetadata`；OM 5xx / 连接失败映射为 `upstream.unavailable`（502）且无任何回退数据；OM 403 映射为权限错误；响应中任何 `password` 字段被替换为 `*********`（防御性）
- [X] T022 实现 `services/bff/src/contexture_bff/adapters/om_sources.py` 的 OM 客户端基础（复用 `contexture_core.mcp.TokenExchanger.exchange`、httpx、trace 传播、错误映射），并在 `services/bff/src/contexture_bff/settings.py` 增加 OM 受众配置、`deploy/charts/bff/values.yaml` 与模板增加对应项（使 T021 通过）
- [X] T023 [P] 在 `services/bff/tests/unit/test_om_user_sync.py` 编写测试（先写、先失败）：按令牌 `realm_access.roles` 计算应在的团队（`admin`、`ai-engineer`，其他角色忽略）；OM 中无此用户时以服务账号令牌创建（用户名 = `preferred_username`）；加入应在、移出不应在的团队；已一致时不发写请求；OM 不可用时登录失败并返回 `upstream.unavailable`，不静默跳过
- [X] T024 在 `services/bff/src/contexture_bff/adapters/om_users.py` 实现服务账号（`contexture-bff` client credentials）令牌获取与用户 / 团队同步，并在 `services/bff/src/contexture_bff/api/auth.py` 的登录回调与会话刷新中调用（使 T023 通过）
- [X] T025 [P] 在 `services/bff/tests/unit/test_audit.py` 编写测试：写操作审计日志含 `trace_id`、`tenant_id`、`user_id`，`action=write`、`resource.kind=api`、`resource.ref` 为“方法 + 实际请求路径”（先提交、先失败）
- [X] T026 在 `services/bff/src/contexture_bff/api/sources.py` 建立路由模块骨架与审计辅助函数，挂载到 `services/bff/src/contexture_bff/main.py`（仅 admin / ai-engineer 可访问）（使 T025 通过）
- [X] T027 [P] 在 `apps/web/src/__tests__/navigation.test.tsx` 编写测试：“数据资产 → 数据源”入口指向 `/sources`（先提交、先失败）
- [X] T028 修改 `apps/web/src/layout/navigation.ts`、`apps/web/src/App.tsx` 新增路由与 `apps/web/src/pages/SourcesPage.tsx` 空壳（使 T027 通过）
- [X] T029 [P] 在 `apps/web/src/__tests__/sources-api.test.ts` 编写测试：BFF 返回 502 时调用方得到带错误码与 trace_id 的错误，不返回任何数据（先提交、先失败）
- [X] T030 在 `apps/web/src/features/sources/api.ts` 基于 `@contexture/ts-api` 封装全部 005 接口；错误一律抛出并携带 BFF 错误码与 trace_id，不得捕获后返回示例数据（使 T029 通过）

**Checkpoint**: 真实链路已验证；BFF 与 Web 公共骨架就绪。

---

## Phase 3: User Story 1 - 接入数据源并完成首次元数据采集 (Priority: P1) 🎯 MVP

**Goal**: 在 `/sources` 查看汇总、用四步向导接入数据源（OM 原生测试连接、过滤规则、按任务调度），保存后由 OM 部署，并在元数据采集任务上触发首采，表与字段写入 OM。

**Independent Test**: 在 MES / QMS / Doris 上完成接入与首采，OM 中准确入库 28 张表 / 198 个字段及主键约束，列表统计与详情一致（quickstart 场景 B）。

### Tests for User Story 1（先写、先失败）

- [X] T031 [P] [US1] 在 `services/bff/tests/contract/test_sources_contract.py` 编写 `listSources`、`createSource`、`getSource`、`updateSource`、`startTestConnection`、`getTestConnection` 的契约测试（请求 / 响应 schema、401 / 403、409 `source.name_conflict`、502 `upstream.unavailable`、密码恒为 `*********`；`updateSource` 请求中 `name` 或 `serviceType` 与已保存值不同时返回 400 `source.immutable_field`）
- [X] T032 [P] [US1] 在 `services/bff/tests/unit/test_source_mapping.py` 编写连接字段映射测试（research R9）：MySQL / Doris 的数据库为选填并映射 `databaseSchema`；PostgreSQL / SQL Server 的数据库必填并映射 `database` 且 `ingestAllDatabases=false`；Oracle 映射 `oracleConnectionType.oracleServiceName`；密码为 `*********` 时不覆盖已存密码
- [X] T033 [P] [US1] 在 `services/bff/tests/unit/test_pipeline_config.py` 编写管道配置测试：三级过滤规则映射到 `databaseFilterPattern` / `schemaFilterPattern` / `tableFilterPattern` 的 `includes` / `excludes`；非法正则（按 Python `re`）返回 400 并指出规则；强制 `markDeletedTables=false`、`overrideMetadata=false`、`extractJsonSchema=false`、不开启 `includeDDL`，请求不能覆盖；任务名为 `<服务标识中非字母数字替换为 _>_metadata_<8 位字母数字>`；`scheduleInterval` 为 cron 或空、时区 `Asia/Shanghai`；服务标识须匹配 `^[a-z][a-z0-9-]{1,49}$`
- [X] T034 [P] [US1] 在 `services/bff/tests/unit/test_test_connection.py` 编写测试：创建 `TEST_CONNECTION` workflow → trigger → 轮询返回步骤（名称、必需 / 可选取自 OM `testConnections/database/<connector>.json`）；完成后删除 workflow；OM 失败时返回真实错误
- [X] T035 [P] [US1] 在 `services/bff/tests/integration/test_sources_cluster.py`（`-m cluster`）编写测试：用真实 OM / Airflow / 003 模拟库创建 MES（数据库填 `mes`，使范围排除同实例的 `viewlab` 库）、QMS（数据库 `qms`）、Doris（数据库 `mock_dw`）数据源并运行元数据采集，断言表数与字段数等于 003 金标准（13 / 79、7 / 53、8 / 66），主键约束存在，Doris 键列为 `PRIMARY_KEY`；`listSources` 统计与之一致
- [X] T036 [P] [US1] 在 `apps/web/src/__tests__/sources-list.test.tsx` 编写组件测试（mock BFF 响应为测试夹具）：4 张统计卡按夹具计算；空列表显示空状态；BFF 错误显示错误与重试，不出现任何示例数据源；搜索与状态筛选（全部 / 采集成功 / 需要关注 / 待配置 / 调度已暂停）
- [X] T037 [P] [US1] 在 `apps/web/src/__tests__/source-wizard.test.tsx` 编写向导测试：服务标识规则与重复拦截；按连接器显示数据库必填 / 选填与 Service Name；测试连接逐步展示（必需 / 可选、通过 / 失败 / 未执行），必需步骤失败或参数变更后不能进入下一步；过滤规则非法正则拦截；“创建视图血缘任务”仅在“采集视图”开启时可选；第 4 步按任务分别设置调度；保存失败显示真实错误

### Implementation for User Story 1

- [X] T038 [US1] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现连接字段映射与管道配置构建（使 T032、T033 通过）
- [X] T039 [US1] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现测试连接 workflow 的创建、触发、查询与清理（使 T034 通过）
- [X] T040 [US1] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现数据源列表 / 详情 / 新建 / 修改：保存 `DatabaseService` 与管道后调用 OM `deploy/{id}`，部署失败返回 `source.deploy_failed` 且保留实体；表数 / 字段数按 `tables?service=&fields=columns` 分页实时计算；状态派生按 data-model.md 第 3 节
- [X] T041 [US1] 在 `services/bff/src/contexture_bff/api/sources.py` 实现 `GET/POST /bff/v1/sources`、`GET/PUT /bff/v1/sources/{name}`、`POST /bff/v1/sources/test-connection`、`GET /bff/v1/sources/test-connection/{workflowId}`，写操作记审计（使 T031、T035 通过）
- [X] T042 [P] [US1] 实现 `apps/web/src/features/sources/SourcesWorkspace.tsx` 列表页（页头、4 张统计卡、工具栏、表格、底部提醒卡与采集链路说明）及样式 `apps/web/src/features/sources/sources.css`，结构与文案对齐 `prototype/index.html`，数据全部来自 BFF（使 T036 通过）
- [X] T043 [P] [US1] 实现 `apps/web/src/features/sources/SourceWizardModal.tsx` 四步向导（测试连接轮询，等待期间显示“测试中”）（使 T037 通过）
- [X] T044 [US1] 实现 `apps/web/src/features/sources/SourceDetailView.tsx` 的页头、概览页签（数据源属性只读展示、异常提示条、3 张指标卡、连接信息与各任务调度 / 最近运行）与采集配置页签（三级过滤、视图、视图血缘任务、采集边界）
- [X] T045 [US1] 在 `tests/e2e/sources.spec.ts` 编写并跑通 US1 端到端：真实环境接入 MES（数据库填 `mes`）并首采，列表与详情统计等于 003 金标准；响应中无密码明文

**Checkpoint**: US1 可独立演示（MVP）。

---

## Phase 4: User Story 2 - 管理采集任务、调度启停、运行日志与异常后重新运行 (Priority: P1)

**Goal**: 在“采集任务”页签管理元数据采集与视图血缘两类任务：运行记录、状态筛选、立即运行、暂停 / 恢复、运行详情（步骤统计、失败对象、最近一次日志）。

**Independent Test**: quickstart 场景 C；运行记录与 OM `PipelineStatus` 一致。

### Tests for User Story 2（先写、先失败）

- [X] T046 [P] [US2] 在 `services/bff/tests/contract/test_pipelines_contract.py` 编写 `listPipelineRuns`（含 `state` 筛选）、`triggerPipeline`（202、409 `source.pipeline_in_flight`）、`setPipelineScheduleEnabled`（200、400 `source.schedule_not_set`）、`getLastPipelineLogs` 契约测试；`kind` 仅允许 `metadata`、`lineage`
- [X] T047 [P] [US2] 在 `services/bff/tests/unit/test_pipeline_runs.py` 编写测试：`PipelineStatus` 原样投影为 `PipelineRun`（runId、pipelineState、startDate、endDate、steps 的 records / updatedRecords / warnings / errors / filtered / failures），新到旧排序，无触发方式字段；存在 queued / running 时拒绝触发；暂停 / 恢复调用 OM `toggleIngestion`；日志经脱敏
- [X] T048 [P] [US2] 在 `services/bff/tests/integration/test_pipelines_cluster.py`（`-m cluster`）编写测试：对 MES 元数据采集任务暂停后 Airflow DAG `is_paused=true`、恢复后为 false；立即运行产生新的 `PipelineStatus`；最近一次日志可读
- [X] T049 [P] [US2] 在 `apps/web/src/__tests__/source-tasks.test.tsx` 编写组件测试（夹具数据）：任务列表按 `pipelines` 渲染 1 或 2 条；运行记录列为开始时间 / 状态 / 耗时 / 运行编号；筛选仅作用于当前任务；运行中禁用“立即运行”；暂停确认弹窗；运行详情展示步骤统计与失败对象，仅最近一次运行显示日志，其余注明；异常运行提供“立即运行”

### Implementation for User Story 2

- [X] T050 [US2] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现运行记录读取、触发（含在途校验）、暂停 / 恢复与最近日志（使 T047 通过）
- [X] T051 [US2] 在 `services/bff/src/contexture_bff/api/sources.py` 实现 `/bff/v1/sources/{name}/pipelines/{kind}/runs|trigger|schedule|logs/last`，写操作记审计（使 T046、T048 通过）
- [X] T052 [US2] 在 `apps/web/src/features/sources/SourceDetailView.tsx` 实现采集任务页签：任务列表、任务运行视图（轮询刷新、筛选、暂停 / 恢复确认、调度详情弹窗显示 DAG 标识 = 任务名）与运行详情弹窗（使 T049 通过）
- [X] T053 [US2] 在 `tests/e2e/sources.spec.ts` 增加 US2 端到端：暂停 / 恢复、立即运行、运行详情与日志

**Checkpoint**: US1 + US2 可独立验收。

---

## Phase 5: User Story 3 - 浏览四层元数据目录与独立资产结构详情 (Priority: P1)

**Goal**: 左侧目录树与“已采集元数据”页签按 OM 实体层级浏览；数据库 / Schema / 表进入独立 `METADATA CATALOG` 详情。

**Independent Test**: spec US3 Independent Test；MySQL / Doris 为 `default → <物理库> → <表>`，PostgreSQL 为 `<库> → public → <表>`。

### Tests for User Story 3（先写、先失败）

- [X] T054 [P] [US3] 在 `services/bff/tests/contract/test_catalog_contract.py` 编写 `getCatalogEntity` 契约测试（四种 `entityType`、子项与计数、表的 `tableType` / `constraints` / `columns[].constraint`、404）
- [X] T055 [P] [US3] 在 `services/bff/tests/integration/test_catalog_cluster.py`（`-m cluster`）编写测试：在 US1 采集结果上逐层读取，层级与子项数量与 OM 一致；同名表按完整 FQN 隔离
- [X] T056 [P] [US3] 在 `apps/web/src/__tests__/catalog.test.tsx` 编写组件测试（夹具）：目录树展开与服务节点表数 / “未采集”；资产页眉标、标题、FQN、面包屑只到当前层级、“返回所属数据源”；资产页不显示连接配置、采集页签与源级状态；表详情“选择数据表”切换、结构信息（只显示 OM 实际约束，未提供不伪造）、字段 `PK` 徽章；≤ 850px 时“目录”抽屉

### Implementation for User Story 3

- [X] T057 [US3] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现目录实体读取（服务 / 库 / Schema / 表及子项计数、表字段与约束）
- [X] T058 [US3] 新增 `services/bff/src/contexture_bff/api/catalog.py` 实现 `GET /bff/v1/catalog/{entityType}/{fqn}` 并挂载（使 T054、T055 通过）
- [X] T059 [P] [US3] 修改 `apps/web/src/layout/SecondaryNav.tsx` 渲染四层目录树与移动端抽屉；在 `apps/web/src/features/sources/SourceDetailView.tsx` 实现“已采集元数据”页签
- [X] T060 [US3] 新增 `apps/web/src/features/sources/CatalogAssetDetailView.tsx` 独立资产详情（使 T056 通过）
- [X] T061 [US3] 在 `tests/e2e/sources.spec.ts` 增加 US3 端到端：MES / QMS / Doris 三种层级浏览与面包屑

---

## Phase 6: User Story 4 - 维护数据源与各级资产的治理属性及继承关系 (Priority: P2)

**Goal**: 五个层级编辑治理属性，按 OM 原生继承规则展示来源，重采集不覆盖。

**Independent Test**: spec US4 Independent Test；quickstart 场景 E。

### Tests for User Story 4（先写、先失败）

- [X] T062 [P] [US4] 在 `services/bff/tests/contract/test_governance_contract.py` 编写 `patchCatalogEntity` 与 `getGovernanceOptions` 契约测试（`null` 清空恢复继承；字段仅允许 displayName / description / tags / glossaryTerms；400 校验错误）
- [X] T063 [P] [US4] 在 `services/bff/tests/unit/test_governance.py` 编写测试：转换为 OM JSON Patch；数据产品所属域须与有效业务域（含继承）一致；同一 `mutuallyExclusive` 分类只保留一个标签；保留周期须为 ISO 8601 时长（如 `P30D`、`PT24H`）；继承来源计算——业务域 服务 → 库 → Schema → 表，负责人与保留周期 库 → Schema → 表（数据库不继承服务负责人）
- [X] T064 [P] [US4] 在 `services/bff/tests/integration/test_governance_cluster.py`（`-m cluster`）编写测试：在五个层级写入属性后重新运行元数据采集（`overrideMetadata=false`），属性保持不变；修改数据源连接配置后服务级治理属性保持不变
- [X] T065 [P] [US4] 在 `apps/web/src/__tests__/property-edit.test.tsx` 编写组件测试（夹具）：选项来自 BFF；保存回显、取消不保存、清空恢复继承、“单独设置 / 继承自 <上级类型> · <上级 FQN>”标注、域与产品不匹配提示、互斥标签替换、周期校验、HTML 输入转义

### Implementation for User Story 4

- [X] T066 [US4] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现治理选项读取、属性 Patch 与继承来源计算（使 T063 通过）
- [X] T067 [US4] 在 `services/bff/src/contexture_bff/api/catalog.py` 实现 `PATCH /bff/v1/catalog/{entityType}/{fqn}` 与 `GET /bff/v1/governance/options`，写操作记审计（使 T062、T064 通过）
- [X] T068 [US4] 新增 `apps/web/src/features/sources/PropertyEditModal.tsx`，并接入概览、库 / Schema / 表详情与字段行（使 T065 通过）
- [X] T069 [US4] 在 `tests/e2e/sources.spec.ts` 增加 US4 端到端：五层级编辑、继承与恢复、重采集保留

---

## Phase 7: User Story 5 - 采集数据库视图定义并生成视图血缘 (Priority: P2)

**Goal**: 开启“采集视图”并创建视图血缘任务，lineage 任务依据视图定义写入表级与字段级血缘；视图定义不可读时如实记录、不伪造。

**Independent Test**: quickstart 场景 D，以 viewlab 标准答案核对。

### Tests for User Story 5（先写、先失败）

- [X] T070 [P] [US5] 在 `services/bff/tests/unit/test_lineage_pipeline.py` 编写测试：`createLineageTask=true` 且 `includeViews=true` 时创建 `pipelineType=lineage` 管道，配置 `processViewLineage=true`、`processQueryLineage=false`、`processStoredProcedureLineage=false`，任务名 `<服务>_lineage_<8 位随机串>`、独立调度；`includeViews=false` 时 `createLineageTask=true` 返回 400；修改为关闭时删除 lineage 管道
- [X] T071 [P] [US5] 在 `services/bff/tests/integration/test_view_lineage_cluster.py`（`-m cluster`）编写测试：viewlab（MySQL；PostgreSQL 视 T019 结论）先运行元数据采集再运行视图血缘，OM 血缘接口中每个视图的上游表与 `columnsLineage` 与 `testdata/mockfactory/viewlab.py` 标准答案完全一致、无多余边；改用受限账号重新采集后表与字段仍入库、不新增血缘边、运行结果如实反映视图定义不可读（以 OM 实际状态为准）

### Implementation for User Story 5

- [X] T072 [US5] 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 实现 lineage 管道的创建、部署、调度与删除（使 T070、T071 通过）
- [X] T073 [US5] 在 `apps/web/src/features/sources/SourceWizardModal.tsx` 与 `SourceDetailView.tsx` 中联通视图血缘任务的创建、调度与任务列表展示（复用 US2 任务视图）
- [X] T074 [US5] 在 `tests/e2e/sources.spec.ts` 增加 US5 端到端：viewlab 接入、两条任务依次运行、血缘结果与标准答案一致

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T075 [P] 在 `tests/e2e/sources.spec.ts` 增加 1280 / 768 / 390 视口下列表、详情四页签、向导、资产页与属性弹窗的整页横向溢出检查（SC-007）
- [X] T076 [P] 在 `tests/e2e/sources.spec.ts` 增加依赖异常场景：OM 不可用时 `/sources` 显示真实错误、不显示示例数据（quickstart 场景 F）
- [X] T077 [P] 代码审查清单核对：`services/bff/src/`、`apps/web/src/` 中无示例数据源 / 表 / 运行、无失败回退分支、无 Airflow 直连、无源库驱动依赖（`pymysql`、`asyncpg` 等不得出现在 `services/bff/pyproject.toml`）；结果记入 acceptance.md
- [X] T078 测量并记录：列表与目录读取 p95、测试连接耗时、MES 接入到首采完成耗时（SC-002），写入 `specs/005-source-metadata-ingestion/research.md` R11 与 acceptance.md
- [X] T079 运行 `make lint`、`make test`（含覆盖率 ≥ 80%）、`pnpm --filter @contexture/web test`、`make components-check`、`make patches-check`、`make e2e`，全部通过；失败项如实记录原因
- [X] T080 编写 `specs/005-source-metadata-ingestion/acceptance.md`（宪法“开发流程与质量门禁”），内容须包含：前置条件与数据准备（`make up`、`make seed`、`make mock-data` 等）、预计用时；逐步操作与每一步的预期结果，每一步的命令可直接复制执行、不要求验收人另装开发环境以外的工具，产品负责人不读代码即可独立执行；每一步与 US1–US5、SC-001–SC-007 的对应关系；开发方已执行的验证结果（T079 的 `make lint`、`make test` 及覆盖率、`make e2e` 等结论，因环境原因未通过的项写明原因与处理方式）；已知限制至少包括：Oracle / SQL Server 无本地实例仅契约与单元测试覆盖、Doris UNIQUE KEY 不识别（键列显示为主键）、仅提供最近一次运行日志、T019 的 PostgreSQL 结论、T020 中 R5 验证项的结论、T077 代码审查结果、T078 实测耗时；验收记录栏目（日期、验收人、结果、发现的问题）留空待负责人填写

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**：无依赖。
- **Phase 2 Foundational**：依赖 Phase 1；T013 需负责人确认后才能做 T014；**T020 是闸门**，依赖 T007–T014、T018；T021–T030 在 T020 通过后进行。
- **Phase 3–7 用户故事**：全部依赖 Phase 2 完成。
- **Phase 8 Polish**：依赖所需用户故事完成。

### User Story Dependencies

- **US1（P1）**：仅依赖 Foundational；MVP。
- **US2（P1）**：需要已配置的数据源与管道（复用 US1 的 BFF 接口与详情页）；可在 US1 的 T040 完成后并行开发。
- **US3（P1）**：需要 US1 采集出的目录数据做集成测试；BFF / 前端开发可与 US2 并行。
- **US4（P2）**：依赖 US3 的资产详情页承载属性卡片。
- **US5（P2）**：依赖 US1 的向导与 US2 的任务视图；需要 T018 的 viewlab。

### Within Each User Story

- 测试先提交并失败 → 适配器 → 路由 → 前端 → 端到端；故事完成后再进入下一优先级。

### Parallel Opportunities

- Phase 2：T004–T006 并行；T016–T017 并行；T021、T023、T025、T027、T029 并行（各自的实现任务 T022、T024、T026、T028、T030 在对应测试提交后进行）。
- US1：T031–T037 全部可并行编写；T042 与 T043 并行。
- US2 / US3 的测试任务可并行；US3 的 T059 与 US2 的 T052 改动不同文件，可并行。

---

## Parallel Example: User Story 1

```bash
# 先并行编写全部 US1 测试（确认失败后提交）：
Task: "T031 BFF 契约测试 services/bff/tests/contract/test_sources_contract.py"
Task: "T032 连接字段映射单元测试 services/bff/tests/unit/test_source_mapping.py"
Task: "T033 管道配置单元测试 services/bff/tests/unit/test_pipeline_config.py"
Task: "T034 测试连接单元测试 services/bff/tests/unit/test_test_connection.py"
Task: "T036 列表组件测试 apps/web/src/__tests__/sources-list.test.tsx"
Task: "T037 向导组件测试 apps/web/src/__tests__/source-wizard.test.tsx"

# 实现阶段前端两个组件并行：
Task: "T042 SourcesWorkspace.tsx"
Task: "T043 SourceWizardModal.tsx"
```

---

## Implementation Strategy

### MVP First（US1）

1. Phase 1 → Phase 2（含 T020 闸门）。
2. Phase 3（US1）→ 停下来按 quickstart 场景 B 验证 → 可演示。

### Incremental Delivery

1. US1（接入与首采）→ US2（任务控制）→ US3（目录浏览）构成 P1 完整能力。
2. US4（治理属性）、US5（视图血缘）为 P2 增量。
3. 每个故事完成后跑对应端到端与集群测试；最后 Phase 8 统一验收。

### 闸门与回退

- T020 不通过：停止，记录失败点与证据，回到负责人决策（ADR-0006 备选：关闭 OM 编排、仓库内 DAG 运行采集容器）。不得以 BFF 直连源库或伪造状态绕过。

---

## Notes

- `[P]` = 不同文件、无未完成依赖；[Story] 用于追踪到用户故事。
- 每个任务完成后按“测试提交 → 实现提交”的顺序提交，不使用 squash。
- 做不到的部分写入 acceptance.md 已知限制，不用假实现填补。
