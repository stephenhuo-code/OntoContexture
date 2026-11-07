# Research: 源系统元数据采集（005）

**Date**: 2026-11-07 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

首轮实现偏离 OpenMetadata 原生链路，已废弃（BFF 用 bot 令牌取明文密码、自行连库采集、伪造运行状态）。本研究基于锁定源码
`third_party/openmetadata/src`（`ctx/2.0.3`，提交 `b76076bf`）与当前仓库、本地集群核实，结论只写有出处的内容。
源码路径中 `OM` 指 `third_party/openmetadata/src`。

---

## R1：采集编排——OM 原生 Airflow 编排接口 + managed-apis

- **Decision**: 打开 OM 的 pipeline service client（`AirflowRESTClient`），指向平台独立部署的 Airflow 3.3.2；Airflow 安装
  `openmetadata-managed-apis` 插件。部署、触发、暂停 / 恢复、最近日志、测试连接全部经 OM API 完成，BFF 不直接调用 Airflow。
- **Rationale**:
  - ADR-0006 第 1 节首选“OM 仍支持外部 Airflow 编排接口时使用该接口，OM 中保留采集状态与触发能力”。
  - `OM/openmetadata-service/.../clients/pipeline/airflow/AirflowRESTClient.java:170` 自动识别 Airflow 3.x 并使用
    `/pluginsv2/api/v2`；managed-apis 提供 `deploy`、`trigger`、`status`、`last_dag_logs`、`run_automation` 等路由
    （`OM/openmetadata-airflow-apis/openmetadata_managed_apis/api/routes/`）。
  - 官方采集镜像 `OM/ingestion/Dockerfile:3` 为 `FROM apache/airflow:3.3.2-python3.12`，与平台 Airflow 版本完全一致。
- **Alternatives considered**:
  - BFF 直接调 Airflow REST：首轮做法，绕开 OM 状态与凭证托管，违反 FR-004 / FR-010，否决。
  - 关闭 OM 编排、仓库内自写 DAG 运行采集容器（ADR-0006 备选）：仅在 R1 验证失败时启用，失去 OM 原生部署 / 触发 / 测试连接。
  - OM `K8sPipelineClient`（不经 Airflow）：违反 ADR-0006“Airflow 为唯一编排器”，否决。
- **Risk / 验证**: 上游参考部署是单容器（`OM/ingestion/ingestion_dependency.sh` 同时起 api-server、dag-processor、scheduler），
  平台用 Helm Chart + KubernetesExecutor 分组件部署，需在实施第一阶段用 demo 数据源走通“部署 → 触发 → 状态回写 → 日志”（见 plan 阶段 A）。

## R2：Airflow 镜像

- **Decision**: 新增织境 Airflow 镜像 `contexture/openmetadata-ingestion-airflow:2.0.3-ctx.0`，以上游 `ingestion/Dockerfile`
  的方式构建（基础镜像 `apache/airflow:3.3.2-python3.12`，安装 managed-apis 与 ingestion），但从子仓库源码安装（参照
  `ingestion/Dockerfile.ci`），保证镜像与锁定提交及未来补丁一致；连接器依赖只装本期五类（`mysql`、`postgres`、`oracle`、
  `mssql`、`doris`，见 `OM/ingestion/setup.py`）。Airflow 所有组件与 KubernetesExecutor 任务 Pod 使用同一镜像。
  `third_party/openmetadata/build/build.sh` 增加对应构建目标，纳入离线包。
- **Rationale**: ADR-0011 要求从织境维护的 OM 仓库构建镜像；上游 Dockerfile 从 PyPI 安装，无法携带织境补丁。
  现有 `build.sh ingestion` 目标构建的是 `ingestion/operators/docker/Dockerfile`（`python:3.12-slim`，供 K8s 客户端用），不含 Airflow 与 managed-apis，不适用。
- **Alternatives considered**: 直接用上游 `openmetadata/ingestion` 镜像——违反 ADR-0011 供应链要求；安装全部连接器（`all`）——镜像体积大，本期不需要。

## R3：Airflow 与 OM 的认证

- **Decision（2026-11-07 实施时修订）**: 沿用 Airflow Chart 1.22 的默认认证管理器 FAB（`config.core.auth_manager`），开启
  `AIRFLOW__FAB__AUTH_BACKENDS=…fab.auth_manager.api.auth.backend.basic_auth,…session`；由 Chart 的 createUserJob 创建 OM 专用
  Airflow 用户 `openmetadata`（Admin 角色），密码取已有 Secret `om-secrets/airflow-password`（`tools/up.sh:65`），并删除 Chart
  默认的 `admin/admin`。OM 侧 `pipelineServiceClientConfig.airflow.auth.username/password` 使用同一凭证。
- **Rationale**: `AirflowRESTClient` 只支持用户名 + 密码的 Basic 认证（`AirflowRESTClient.java:85-89,160`）；managed-apis 在
  Airflow 3 下不做自身鉴权，依赖 Airflow 的 Web 认证层（`openmetadata_managed_apis/utils/security_compat.py`）。Chart 默认即 FAB，
  改用 SimpleAuthManager（上游单容器入口脚本 `ingestion_dependency.sh:31-42` 的做法）需额外改 Chart 配置，且与现有集群不一致。
- **验证**: 阶段 A 冒烟检查不带凭证访问 managed-apis 写接口须被拒绝。
- **Alternatives considered**: SimpleAuthManager——上游单容器做法，与 Chart 默认不一致，未采用。

## R4：DAG 文件与生成配置的共享存储

- **Decision**: managed-apis 在 api-server 内写 DAG 文件（`AIRFLOW_DAGS_FOLDER/<dag_id>.py`）与配置（`DAG_GENERATED_CONFIGS/<dag_id>.json`，
  `OM/openmetadata-airflow-apis/openmetadata_managed_apis/operations/deploy.py:112,179`），dag-processor、scheduler 与任务 Pod 都要读到。
  用 Airflow Chart 的 `dags.persistence` 挂一个 PVC，`DAG_GENERATED_CONFIGS` 指到同一卷的子目录。
  - 本地 kind：默认 StorageClass 为 `rancher.io/local-path`（只支持 RWO，已核实 `kubectl get sc`），因此本地环境把 Airflow 各组件与
    KubernetesExecutor 任务 Pod 固定到同一节点（nodeSelector / pod template），由同一节点共享 RWO 卷。
  - 阿里云 ACK：使用 NAS（RWX）StorageClass，不固定节点。
- **Rationale**: 宪法 VI 定制顺序“配置优先”；只改 Helm values，不引入新组件。
- **Alternatives considered**: 新增 NFS provisioner——本地多一个组件；git-sync——DAG 由 OM 动态生成，不在仓库中，不适用；
  LocalExecutor——违反 ADR-0006（KubernetesExecutor）。

## R5：BFF 调用 OM 的身份（负责人 2026-11-07 决定：用户委托令牌）

- **Decision**: 数据源、采集任务、测试连接与目录治理相关的 OM 调用，BFF 使用**登录用户的委托令牌**：经 Keycloak 令牌交换
  （RFC 8693，复用 `packages/py-core/src/contexture_core/mcp.py` 的 `TokenExchanger.exchange(subject_token, audience)`）
  得到受众为 `contexture-openmetadata` 的短期令牌后调用 OM。不再使用 `ingestion-bot` 令牌做这些操作。
  - Keycloak：`contexture-bff` 客户端增加 `contexture-openmetadata` 受众映射（`deploy/components/keycloak/config/contexture.yaml`），
    并增加一个把织境 realm 角色写入扁平声明的 mapper，供 OM 的 `jwtTeamClaimMapping` 使用。
  - OM：`authenticationConfiguration.jwtTeamClaimMapping` 指向该声明（OM 原生：登录时按声明值把用户加入同名团队，
    `OM/openmetadata-spec/.../configuration/authenticationConfiguration.json`）；由 `tools/om_config.py` 创建团队 `admin`、`ai-engineer`
    及仅含数据源 / 采集 / 目录治理所需操作的 OM 角色与策略。
- **Rationale**:
  - OM 只对 bot 身份返回明文凭证：`DefaultAuthorizer.shouldMaskPasswords` 返回 `!subjectContext.isBot()`
    （`OM/openmetadata-service/.../security/DefaultAuthorizer.java:153-156`），服务响应经 `ServiceEntityResource.decryptOrNullify` 脱敏。
    用户令牌下 BFF 只能看到 `*********`，从机制上满足 FR-010“BFF 不持有业务库密码”。
  - 宪法 IV：代表人的调用携带人的身份；OM 自身的变更记录归属到真实用户。
  - OM 已配置 Keycloak `custom-oidc`（`deploy/components/openmetadata/values/base.yaml:53-59`），可校验 Keycloak 签发的令牌。
- **Alternatives considered**: 专用非 bot 服务账号——配置更少，但 OM 变更不归属到人，负责人未采用。
- **Risk / 验证（阶段 A 必须验证）**:
  1. OM 校验 API 令牌时首次出现的用户是否自动建档、`jwtTeamClaimMapping` 在 API 调用（而非 UI 登录）时是否生效；
     不生效时的原生替代：用户首次登录 OM 界面完成建档与入组，或由 `tools/om_config.py` 预置团队成员。
  2. 更新已有服务、密码保持 `*********` 时 OM 是否保留原密码（`ServiceEntityResource.unmask`，`:88-98`）。
  3. 对已有服务测试连接（密码为掩码）时 OM 是否按服务名补全凭证。

## R6：测试连接

- **Decision**: BFF 创建 OM automation workflow（`POST /api/v1/automations/workflows`，类型 `TEST_CONNECTION`，请求含连接配置），
  再 `POST /api/v1/automations/workflows/trigger/{id}`；随后轮询 `GET /api/v1/automations/workflows/{id}` 读取 `status` 与 `response.steps`
  （`OM/openmetadata-service/.../resources/automations/WorkflowResource.java:78,365`）。完成后删除该 workflow。
  步骤定义以 `OM/openmetadata-service/src/main/resources/json/data/testConnections/database/<connector>.json` 为准。
- **Rationale**: managed-apis 的 `run_automation` 在 Airflow api-server 进程内调用 `metadata.automations.execute_runner.execute` 执行
  （`run_automation.py:54-75`），不起任务 Pod；凭证只在 OM 与 Airflow 之间流转，BFF 不碰源库。
- **Alternatives considered**: BFF 直连源库测试——首轮做法，违反 FR-010，否决。

## R7：OM 接口清单（BFF 适配层只用这些公开接口）

| 用途 | OM 接口（`/api/v1` 下） | 出处 |
| --- | --- | --- |
| 数据源增改查 | `PUT/GET /services/databaseServices`、`/services/databaseServices/name/{fqn}` | DatabaseServiceResource |
| 采集任务增改 | `PUT /services/ingestionPipelines`（`pipelineType` = `metadata` / `lineage`） | IngestionPipelineResource:122 |
| 部署到 Airflow | `POST /services/ingestionPipelines/deploy/{id}` | :743 |
| 立即运行 | `POST /services/ingestionPipelines/trigger/{id}` | :823 |
| 暂停 / 恢复 | `POST /services/ingestionPipelines/toggleIngestion/{id}` | :848 |
| 运行记录 | `GET /services/ingestionPipelines/{fqn}/pipelineStatus?startTs&endTs` | :1341 |
| 最近一次日志 | `GET /services/ingestionPipelines/logs/{id}/last` | :1128 |
| 测试连接 | `/automations/workflows`、`/automations/workflows/trigger/{id}` | WorkflowResource:78,365 |
| 目录与治理属性 | `GET /databases`、`/databaseSchemas`、`/tables`（含 `fields`）、`PATCH /{entity}/{id}`（JSON Patch） | 各实体 Resource |
| 治理选项 | `GET /users`、`/teams`、`/domains`、`/dataProducts`、`/classifications`、`/tags`、`/glossaries`、`/glossaryTerms` | 各实体 Resource |

- **日志**：默认日志存储忽略 runId、始终返回最近一次运行日志（`OM/openmetadata-service/.../logstorage/DefaultLogStorage.java:70-82`）；
  按次日志需 S3 日志存储，本期不做，与 spec 一致。

## R8：采集管道配置

- 元数据采集：`sourceConfig.config.type=DatabaseMetadata`，`includeViews` 按向导，`databaseFilterPattern` / `schemaFilterPattern` /
  `tableFilterPattern` 按向导，强制 `markDeletedTables=false`、`includeDDL` 不开启、`overrideMetadata=false`；不创建 profiler / 采样类管道；
  `extractJsonSchema` 保持关闭（`databaseServiceMetadataPipeline.json`）。
- 视图血缘：`sourceConfig.config.type=DatabaseLineage`，`processViewLineage=true`、`processQueryLineage=false`、
  `processStoredProcedureLineage=false`（默认值为 true，必须显式关闭；`databaseServiceQueryLineagePipeline.json`）。
- 任务命名：`<服务标识中非字母数字替换为 _>_<metadata|lineage>_<8 位随机串>`（OM 前端 `ServicePureUtils.getIngestionName`）；
  DAG 标识为管道名（managed-apis `common.py:281` `clean_dag_id`）。
- 运行状态：`PipelineStatus` 字段 `runId`（UUID）、`pipelineState`（queued / running / success / partialSuccess / failed / stopped）、
  `startDate`、`endDate`、`status`（StepSummary：records / updated_records / warnings / errors / filtered / failures）。无触发方式字段。

## R9：连接字段按连接器映射（spec Clarification 2026-11-07）

| 向导字段 | MySQL / Doris | PostgreSQL | SQL Server | Oracle |
| --- | --- | --- | --- | --- |
| 主机 + 端口 | `hostPort` | `hostPort` | `hostPort` | `hostPort` |
| 用户名 | `username` | `username` | `username` | `username` |
| 密码 | MySQL `authType.password`；Doris `password` | `authType.password` | `password` | `password` |
| 数据库 | 选填 `databaseSchema` | 必填 `database`，`ingestAllDatabases=false` | 必填 `database`，`ingestAllDatabases=false` | `oracleConnectionType.oracleServiceName` |
| TLS | `sslConfig`（按连接器原生字段，具体键在阶段 A 核对） | `sslMode` | `encrypt` | 本期不暴露 |

出处：`OM/openmetadata-spec/.../entity/services/connections/database/{mysql,postgres,mssql,oracle,doris}Connection.json`。

## R10：测试数据

- 003 的 MES / QMS 仅有 root 账号（`testdata/deploy/secrets.sh`），Doris 已有只读账号（`testdata/mockfactory/load/doris.py:47-50`）。
  本期为 MES（MySQL）与 QMS（PostgreSQL）补充只读元数据账号，不改动 003 的表与数据。
- 视图测试库（spec Clarification 2026-11-07）：在 mock-mes MySQL 与 mock-qms PostgreSQL 实例内各新建独立数据库 `viewlab`，
  含基表与引用基表的视图（表级与字段级映射有确定的标准答案），以及两个账号：可读视图定义的只读账号、读不到视图定义的受限账号。
  - MySQL：受限账号不授予 `SHOW VIEW`，视图定义不可读（MySQL 原生权限）。
  - PostgreSQL：`information_schema.views.view_definition` 对非属主返回空，但 `pg_get_viewdef` 对所有人可读；OM Postgres 连接器取视图定义
    所用查询需在阶段 A 核对，若无法用权限复现“不可读”，该场景以 MySQL 验收并在 acceptance.md 中如实注明。
  - **2026-11-07 核对结论（T019）**：OM Postgres 连接器以 `pg_class` + `pg_get_viewdef(c.oid, true)` 读取视图定义
    （`OM/ingestion/.../source/database/postgres/queries.py:111-120` `POSTGRES_VIEW_DEFINITIONS`），任何可连接角色均可读，
    **PostgreSQL 无法用权限复现“视图定义不可读”**，该场景只用 MySQL 验收；PostgreSQL viewlab 只验证有权限时的视图血缘。
    MySQL 经 SQLAlchemy `inspector.get_view_definition`（`common_db_source.py:468`）读取，需要 `SHOW VIEW`，受限账号
    `viewlab_noview` 可复现（集成测试已验证 `SHOW CREATE VIEW` 被拒、`information_schema.VIEWS` 定义为空）。
  - 随 `make mock-data` 部署；放在 `testdata/` 下，不进入客户交付物。

## R11：性能与等待

- 测试连接在 Airflow api-server 进程内执行，预计秒级；采集运行需拉起任务 Pod，含镜像与 Pod 启动耗时。
  首轮计划“测试连接 p95 ≤ 3s”无依据，改为阶段 A 实测后在 acceptance.md 记录；SC-002（3 分钟完成接入与首采）作为验收目标保留。
- 前端对测试连接与运行状态采用轮询（OM 原生无推送接口给 BFF 使用），间隔与超时在阶段 A 实测后确定。

## R12：OM 团队、角色与策略（负责人 2026-11-07 确认）

- **Decision**: `tools/om_config.py` 幂等创建：
  - 团队 `admin`、`ai-engineer`（由登录令牌中的织境 realm 角色声明经 `jwtTeamClaimMapping` 入组），默认角色均为 `ContextureSourceManager`；
  - 角色 `ContextureSourceManager` → 策略 `ContextureSourcePolicy`，三条 allow 规则（操作名取自
    `OM/openmetadata-spec/.../entity/policies/accessControl/resourceDescriptor.json`）：
    1. `databaseService`：`Create`、`ViewAll`、`EditAll`、`Deploy`、`Trigger`（不含 `Delete`）；
    2. `ingestionPipeline`、`workflow`：`Create`、`ViewAll`、`EditAll`、`Deploy`、`Trigger`、`Delete`
       （删除仅用于关闭视图血缘任务与清理测试连接临时 workflow）；
    3. `database`、`databaseSchema`、`table`：`ViewAll`、`EditAll`（业务域、数据产品、保留周期没有单独操作，只能用 `EditAll`）。
  - 用户、团队、业务域、数据产品、分类、标签、术语的读取沿用 OM 默认 Organization 策略，不另授权；不授予创建治理实体的权限。

## R13：OM 用户与团队的同步（负责人 2026-11-07 选择方案 A：织境登录时同步）

- **事实（源码核实，R5 验证项 1 的结论）**：OM 只在自身界面登录流程中即时建档并按 `jwtTeamClaimMapping` 入组
  （`OM/openmetadata-service/.../security/AuthenticationCodeFlowHandler.java:258,954`）；API 调用经 `JwtFilter` 与
  `DefaultAuthorizer.getSubjectContext` 查找用户，不存在即拒绝，不建档、不入组。OM 开源版 SCIM 接口均返回
  `notImplemented()`（`OM/openmetadata-service/.../scim/impl/DefaultScimProvisioningService.java`），无现成持续同步。
- **Decision**：
  - 织境登录回调（以及会话刷新）时，BFF 按登录令牌 `realm_access.roles` 中的 `admin` / `ai-engineer` 在 OM 中
    幂等建档（用户名 = `preferred_username`）并同步其在团队 `admin`、`ai-engineer` 中的成员身份（加入应在的、移出不应在的）。
  - 建档身份：`contexture-bff` 机密客户端开启服务账号（client credentials，无需新密钥），OM 中对应普通（非 bot）用户
    `service-account-contexture-bff` 由 `tools/om_config.py` 预置，只授予角色 `ContextureUserProvisioner`：
    `user`：`Create`、`ViewAll`、`EditTeams`；`team`：`ViewAll`、`EditUsers`。该身份看不到源库密码，也不能操作数据源。
  - 不再使用 OM `jwtTeamClaimMapping`，删除 Keycloak 扁平角色声明 `contexture_roles`。
- **撤销语义**：BFF 每个请求按 Keycloak 令牌角色校验 admin / ai-engineer，角色撤销后在织境立即失效；OM 中残留的团队
  成员身份在下次登录时清除；浏览器只经 BFF 访问 OM，残留身份不可用。Keycloak 中删除的用户在 OM 中不自动删除（本期不做）。
- **Alternatives considered**：定时同步（延迟、多一个任务与 Keycloak 管理凭证）；部署时同步（不自动）；专用服务账号（OM 变更不归属到人）。
