# Research: 平台技术架构与代码架构基座

本文件记录 001 plan 阶段的架构决策。输入为已接受的 ADR 与宪法 v1.5.0。
跨多个特性的决策另成 ADR（0007–0010，状态“提议”，经架构评审后改为“已接受”）。

## R1 服务划分

- **Decision**：Phase 1 只自建 **`bff`** 一个后端服务，另有前端 `web` 与管线任务镜像 `pipelines`；二期增加
  `metric`、`explore`。其余能力复用 Keycloak、OpenMetadata、Langfuse、Airflow、AI 网关、MCP Toolbox
  （ADR-0012、0013）。架构见 `docs/architecture/platform-architecture.md`。
- **Rationale**：逐项核对后，身份（Keycloak）、本体与上下文（OM 术语库、资产 AI 上下文、上下文中心、MCP）、
  轨迹（Langfuse）、管线（Airflow + OM 采集框架）都由已有框架承担；取数由 AI 网关（令牌、授权、路由、审计）
  加 MCP Toolbox（连接数据库、执行只读查询）承担，不再自建 `sql-gateway`；`bff` 是浏览器的唯一入口。
- **Alternatives**：自建薄 `sql-gateway`（ADR-0013 spike 不通过时的后备）；每特性一个服务（约 20 个）——服务间
  耦合多、运维成本高；模块化单体——违反宪法 II 的独立部署与数据独占要求。

## R2 服务间通信

- **Decision**：
  - 同步：HTTP + JSON，接口以 OpenAPI 3.1 契约先行，URL 带主版本（`/v1`）。
  - 异步：Phase 1 **不引入消息中间件**。批处理与定时任务由 Airflow 编排（ADR-0006）；需要响应 OM
    变化的服务（如审批通过后让本体版本生效）订阅 OM 事件（Webhook，自带失败重试与偏移同步）。
  - 审批：不设审批服务，统一使用 OM 治理工作流与任务（ADR-0008）。
  - Agent 访问：上下文与实例数据一律经 AI 网关以 MCP 访问（OM 内置 MCP、MCP Toolbox，ADR-0013）。
- **Rationale**：Phase 1 的异步场景少且多为批处理；Kafka 等中间件会显著增加离线交付与运维成本；
  OM 事件订阅已提供可靠投递，审批流程复用 OM，架构保持最简。
- **Alternatives**：Kafka（重）、NATS JetStream（Apache 2.0，轻）——二期若事件量上升优先评估 NATS。

## R3 跨切面能力的实现位置

- **Decision**：**公共库为主 + 边缘网关为辅**，Phase 1 不引入服务网格。
  - 公共库 `contexture-core`（Python）嵌入每个服务与管线：令牌验证与请求上下文（人 / Agent，`tenant_id` 为部署常量）、
    OTel 初始化与关联属性、本体读取（`ontology`）、MCP 取数客户端与令牌交换（`mcp`）、统一错误格式、配置加载。
  - 边缘网关：Kubernetes Gateway API 的实现（Envoy Gateway，Apache 2.0），负责 TLS、路由、限流。
- **Rationale**：全部服务与管线为 Python，一份公共库即可覆盖；Phase 1 不做数据层授权（宪法 IV 例外）。服务网格对 Phase 1 规模而言复杂度过高。
- **Alternatives**：边车或服务网格（Istio / Linkerd）统一鉴权——缺少业务语义且运维复杂；
  ingress-nginx——社区已宣布退役（需核实时间点），不选。

## R4 令牌在平台内的传递

- **Decision**（ADR-0013）：
  - 人经 Keycloak OIDC（授权码 + PKCE）登录。
  - 每个 Agent（以及 `bff`）在 Keycloak 中是一个客户端。代表人调用时，以自己的客户端身份对人的令牌做
    **标准令牌交换**：新令牌 `sub` = 人、`azp` = Agent、`aud` 收窄到目标（AI 网关等）、有效期短。人的登录令牌
    经受众映射包含这些客户端。客户端密钥由 Omnigent 服务端与 `bff` 保管，不下发给 Agent 执行进程。
  - 每个服务用 Keycloak 的 JWKS 本地验签；交换按会话与目标缓存，不在每一跳重复。
  - 无人值守任务（Airflow 管线、自演进）：以服务账号用 client credentials 取令牌。
- **Rationale**：令牌中有签名的人与 Agent，满足宪法 IV；受众收窄符合 MCP 授权规范，Agent 拿不到人的全部权限；
  只用 Keycloak 正式支持的功能。
- **Alternatives**：Agent 直接携带人的登录令牌——分不出人与 Agent；Keycloak 委托交换（`act` 声明）——预览
  状态，二期写回时再评估。

## R5 多租户隔离 → ADR-0007（Phase 1 单租户）

- **Decision**：Phase 1 按单租户设计与交付：一套环境只服务一个客户，可有多个用户与 Agent；`tenant_id` 作为部署
  常量写入审计、追踪与日志；Keycloak 一个 realm，不用 Organization；各组件各一份（宪法 v1.5.0 部署约束的
  Phase 1 例外，ADR-0007 修订）。ADR-0007 原多租户设计（Organization、每租户 database / project / 域等）暂缓，是否采用另行评估。
- **Rationale**：Phase 1 只有一个 POC 客户；单租户可去掉网关租户路由、OM 域隔离、Omnigent 多租户改造与跨租户
  测试，显著降低工作量；保留 `tenant_id` 字段使二期改造不影响数据格式。
- **Alternatives**：Phase 1 即共享实例多租户——工作量大且 POC 用不上；不保留 `tenant_id`——将来如需多租户须迁移审计与追踪数据。

## R6 本体六要素的实现 → ADR-0008

- **Decision**：**不改 OpenMetadata 核心，直接使用 OM 的本体能力。** Phase 1 只做对象、关系、属性（含映射），
  全部建为 OM 术语；审批用 OM 术语审批工作流；`bff` 直接读写 OM；公共库 `contexture-core.ontology` 经 OM API
  读取已审批的本体并按租户过滤；开启 OM 的 RDF 能力（OM 同步到 Fuseki），用 OM 的 SPARQL 接口验证本体功能
  与性能。不另建本体服务、本体存储与编译链路；接口、逻辑、动作放到二期。
- **Rationale**：Phase 1 只需对象、关系、属性，OM 原生能承载；复用最大、架构最简。
- **Alternatives**：Phase 1 即实现六要素并建 ontology 服务——用不到；织境另建 Fuseki 数据集并编译写入 OWL——
  Phase 1 用 OM 自带能力即可验证；改 OM 核心——补丁大。

## R7 仓库结构与代码架构 → ADR-0009

- **Decision**：monorepo；Python 用 uv workspace，前端用 pnpm workspace；目录与服务内分层见 plan.md
  “代码架构”；开源组件每个一个标准目录（清单 + CI 检查）；Phase 1 不做服务模板，`bff` 为参考实现，二期再从
  `bff` 提炼 Copier 模板。
- **Rationale**：公共库、契约、本体、部署描述需要与服务同步演进；单仓便于一次 PR 内完成跨服务变更与
  回归。
- **Alternatives**：多仓（每服务一仓）——公共库与契约版本协调成本高。

## R8 接口契约与版本

- **Decision**：OpenAPI 3.1 文件放 `contracts/openapi/<服务>.yaml`，先评审后实现；CI 用 oasdiff
  （Apache 2.0）检测破坏性变更，用 Schemathesis（MIT）对服务做契约测试；同一主版本内只允许新增；
  事件与审计记录用 JSON Schema 放 `contracts/schemas/`；OTel 关联属性规范放 `contracts/otel/`。
  前端 API 客户端由 OpenAPI 生成（openapi-typescript，MIT）。
- **Rationale**：落实宪法 II“契约先行、向后兼容”。

## R9 Python 技术栈

- **Decision**：Python 3.12；FastAPI；Pydantic v2；SQLAlchemy 2 + Alembic；httpx；OpenTelemetry
  Python SDK；pytest + Testcontainers；ruff（格式与静态检查）+ pyright（类型检查）。
- **Rationale**：与 ADR-0006（Airflow DAG 为 Python）、OM 采集框架（Python）一致。

## R10 存储与基础组件许可

- **Decision**：
  - PostgreSQL：一个集群，每个服务独占一个 database（宪法 II）。
  - Doris：本体实例库（ADR-0004）+ 审计库（`audit` database，只追加）。
  - 对象存储：测试环境用阿里云 OSS（经 S3 兼容接口）；发布验证与客户离线环境用 **SeaweedFS**
    （Apache 2.0）。**不选 MinIO（AGPL-3.0，违反宪法 III）**。
  - 缓存与 Langfuse 依赖的 Redis 兼容存储：**Valkey**（BSD-3）。Redis 近年改为非宽松许可，不选。
  - ClickHouse（Langfuse 依赖，Apache 2.0）。
- **Rationale**：宪法 III 只允许宽松许可进入交付物。

## R11 审计的写入与可靠性

- **Decision**：AI 网关对每次 MCP 调用记录人（`sub`）、Agent（`azp`）、租户、工具、查询摘要与 trace_id，经
  OTel Collector 汇聚；返回行数与完整 SQL 由 MCP Toolbox / Doris `audit_log` 补齐，按 trace_id 关联（ADR-0013
  spike 第 3 项确认字段覆盖）。OM 自身记录写操作审计。
- **Rationale**：宪法 IV 的 Phase 1 例外只放宽数据层授权，审计不放松；审计放在统一入口，避免各 MCP 服务分别改造。

## R12 数字员工平台 → ADR-0010（待确认）

- **Decision（提议）**：P1 / P2 以飞书为主要对接平台；织境对外只承诺标准接口——MCP（Streamable
  HTTP，OAuth 授权）与 OM 资产 AI 上下文（OKF v0.2）——保持中立；轨迹回传支持 OTLP 与 Webhook；参考 Agent 用 Omnigent
  （ADR-0002）。
- **待确认**：POC 客户实际使用的飞书 Agent 产品形态及其能否携带用户令牌调用外部 MCP。

## R13 端到端骨架的组成

- **Decision**：骨架使用真实组件的最小配置：`web` 登录 → `bff`（经 `contexture-core.ontology` 从 OM 读取已审批的
  对象定义；以 `bff` 客户端身份交换令牌）→ AI 网关（验签、审计）→ MCP Toolbox（示例参数化查询工具，只读
  账号）→ Doris。单租户部署；Keycloak 预置测试用户与一个示例 Agent 客户端。
- **Rationale**：骨架即后续 004、005、019 的起点，并顺带完成 ADR-0013 spike 的第 1、2、3、5 项。

## R14 CI 与制品

- **Decision**：GitHub Actions（代码已在 GitHub）；镜像推送到阿里云 ACR（测试环境）并随离线包导出；
  门禁按宪法：构建、单元 / 契约 / 集成测试、覆盖率 ≥ 80%、ruff + pyright、SBOM（Syft）、许可扫描
  （ScanCode）、漏洞扫描（Trivy / Grype）。具体在 tasks 准备阶段搭建。

## R15 性能与规模基线

- **Decision**：骨架端到端（本地环境）P95 ≤ 1 秒；AI 网关加 MCP Toolbox 的取数开销（不含查询执行）P95 ≤ 100 毫秒，spike 中测定后确认；平台设计容量为 Phase 1 压测目标 500 个并发 Agent 运行（ADR-0002）。
  具体压测在 005、012 中进行。

## R16 OpenMetadata 的构建与部署 → ADR-0011

- **Decision**：跟随 OM 最新发布版本（当前 2.0.3），从织境维护的 OM 仓库（子仓库，宪法 VI 上游镜像仓库方式）
  构建 `openmetadata-server` 与 `openmetadata-ingestion` 镜像，Phase 1 不改源码；用织境自己的 Helm Chart 独立部署，依赖组件使用平台共享的
  PostgreSQL、OpenSearch、Fuseki（OM 的 RDF 存储）、对象存储与独立的 Airflow。
- **Rationale**：供应链可控（SBOM、扫描）、离线与多环境交付、快速跟随上游，与宪法 VI 的 `third_party/`
  机制一致。
- **Alternatives**：直接使用官方镜像与依赖打包 Chart——版本与配置受官方节奏约束，离线打包不可控。

## R17 Phase 1 精简自建服务 → ADR-0012

- **Decision**：取消 `iam`、`graph`、`context`、`trace`、`ingest`；`gateway` 改名 `sql-gateway`（随后由 R18 取消）；上下文复用 OM
  （OKF 升级到 v0.2 以补丁实现）；轨迹复用 Langfuse；管线由 Airflow 承载、用户可自定义；数据层授权推迟到二期
  （宪法 v1.3.0 原则 IV 例外）。
- **Rationale**：先把已有框架的能力用好，只自建框架不具备的能力。

## R18 数据访问与 AI 网关 → ADR-0013

- **Decision**：Agent 取数一律经 MCP。AI 网关（agentgateway 或 Agent Router，spike 选定）统一校验令牌、按工具
  授权、路由与审计，并兼作模型网关；数据库后端统一用 MCP Toolbox（Phase 1 单租户，一个实例，只读账号），Doris 优先
  用其 mysql 数据源，不可行时用 Apache Doris MCP Server。不自建 `sql-gateway`；不用 LiteLLM 作网关。
- **Rationale**：主流数据库普遍提供 MCP 服务，但身份、审计、租户路由没有统一，集中由网关配置完成；一条取数路径
  覆盖 Doris 与客户的各种数据库。
- **Alternatives**：自建薄 `sql-gateway`（后备）；Doris OIDC 插件；OM Query Runner（开源版无执行部分）；Trino、
  Kyuubi、Spice（偏重或关键能力收费）；LiteLLM（认证与审计需商业许可）。
