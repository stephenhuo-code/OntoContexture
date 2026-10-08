# 织境平台技术架构（Phase 1）

2026-10-08 · 依据：宪法 v1.4.0、ADR-0001 至 ADR-0013、`specs/001-engineering-foundation/`

## 1. 架构原则

1. **先把已有框架的能力用好**：OpenMetadata、Keycloak、Langfuse、Airflow、Omnigent、AI 网关、MCP Toolbox 以独立服务集成，按
   “配置 → 扩展 → 补丁”逐级定制（宪法 VI），不额外增加新的能力（ADR-0012）。
2. **只自建框架不具备的能力**：Phase 1 自建服务只有 `bff`（ADR-0013）。
3. **Agent 取数一律经 MCP**：经 AI 网关统一校验令牌、授权、路由与审计，数据库后端用 MCP Toolbox（ADR-0013）。
4. **审批只有一套**：统一使用 OM 治理工作流与任务。
5. **管线可由用户自定义与运维**：数据管线统一在 Airflow 中运行。
6. **架构保持最简**：不引入消息中间件、不建服务网格；Phase 1 只读，数据层授权推迟到二期（宪法 IV 例外）。

## 2. 总览

```text
访问层
  浏览器（织境 Web）                         客户数字员工平台 / 客户侧 Agent（Omnigent）
        │ OIDC + PKCE                              │ MCP（交换后的令牌）；OTLP / Webhook 回传轨迹
        ▼                                          ▼
边缘网关（Envoy Gateway，Gateway API）
        │                                          │                                  │
        ▼                                          ▼                                  ▼
  bff（织境自建）                     AI 网关（MCP 网关 + 模型网关）               OTel Collector
   ├─ 本体读写、审批待办 ──► OM API      校验令牌、按租户与工具授权、路由、审计          │
   ├─ 决策轨迹页面 ──► Langfuse API ◄─────────────────────────────────────────────────┘
   ├─ Omnigent 会话代理                   ├─► MCP Toolbox（每租户一个实例，只读账号）──► Doris 本体实例库、客户数据库
   └─ 页面取数（MCP 客户端）──► AI 网关    ├─► OM 内置 MCP
                                          ├─► 其他数据库 MCP 服务（按需）
                                          └─► 大模型（私有化模型 / 模型服务）

平台底座（第三方服务）
  OpenMetadata  本体（术语库）、元数据与血缘、治理工作流与任务、上下文中心、资产 AI 上下文（OKF v0.2，
                织境补丁）、内置 MCP；RDF 同步到 Fuseki
  Keycloak      身份、租户（Organization）、角色；Agent 为客户端，标准令牌交换（sub = 人，azp = Agent）
  AI 网关       agentgateway 或 Agent Router（spike 选定）：MCP 与模型流量的统一入口
  MCP Toolbox   数据库 MCP 服务：参数化查询工具与只读 SQL
  Langfuse      决策轨迹、人工修订、样本数据集
  Airflow       管线编排 ──► pipelines 任务镜像：OM 元数据采集、源系统接入与物化（直连 Doris 写入）、飞书同步
                （含修订写回 Langfuse）、文档解析、治理检查、生成 Doris 表结构
  Omnigent      内部 Agent 运行时 ──► agent-sandbox；上下文与取数经 AI 网关（MCP）
  存储与基础    PostgreSQL · OpenSearch · Fuseki · Valkey · 对象存储（OSS / SeaweedFS）
```

## 3. 自建部分

| 组件 | 职责 | 承载特性 | 独占存储 | 对外接口 | 主要依赖 |
| --- | --- | --- | --- | --- | --- |
| `web` | 织境 Web | 003、018 等页面 | — | 浏览器 | `bff` |
| `bff` | 浏览器唯一入口；本体读写；审批待办；轨迹页面；Omnigent 代理；页面取数（经 AI 网关） | 003、009（轨迹页面）、011（本体读写） | Valkey（会话） | REST + SSE（仅浏览器） | OM、Langfuse、Omnigent、AI 网关 |
| `pipelines`（镜像） | Airflow 任务 | 010、011、012、014、016 | 不独占（写入各自目标） | Airflow 任务 | Airflow、OM、Langfuse、Doris |
| 公共库 `contexture-core` | 令牌验证与上下文、令牌交换客户端、可观测关联属性、本体读取（`ontology`）、统一错误格式、配置 | 全部 | — | Python 库 | — |
| 配置即代码 | Keycloak realm 与 Agent 客户端、AI 网关路由与策略、MCP Toolbox 工具定义（含追溯查询模板） | 002、006、015 | — | 配置文件 | — |
| `metric`、`explore`（P2） | 指标生成 SQL；探索与固化 | 020–023 | 二期确定 | REST / MCP | OM、AI 网关 |

**复用框架、不建服务的特性**：002 身份（Keycloak + 配置即代码）；005 分类分级与审计（OM 分类标签 + AI 网关
审计，数据层授权推迟）；006 数据访问（AI 网关 + MCP Toolbox）；007 执行沙箱（agent-sandbox + Omnigent 扩展）；
008 内部 Agent 运行时（Omnigent）；009 决策轨迹（Langfuse）；010 / 012 接入（Airflow + OM 采集框架）；011 本体
（OM 术语库）；013 质量领域包（本体内容）；015 追溯（Toolbox 参数化查询工具）；016 / 017 上下文（OM 上下文中心、
资产 AI 上下文、MCP，OKF v0.2 补丁）；019 / 024 参考 Skill。

## 4. 第三方组件

| 组件 | 部署单元 | 集成方式 | 许可 |
| --- | --- | --- | --- |
| OpenMetadata | `openmetadata-server`、迁移任务；采集任务由 Airflow 拉起 | 从织境维护的 OM 仓库（子仓库）构建、独立部署；Phase 1 补丁仅 OKF v0.2（ADR-0011、0012） | 服务端 Apache 2.0；采集框架与内置 MCP 为 CCL（已批准例外，私有化交付可用）；界面仅内部使用 |
| Keycloak | `keycloak` | 配置（realm 与 Agent 客户端即代码） | Apache 2.0 |
| AI 网关 | agentgateway 或 Agent Router（spike 选定） | 配置（路由、令牌校验、CEL 授权、审计） | Apache 2.0 |
| MCP Toolbox | 每租户一个实例 | 配置（数据源与工具定义） | Apache 2.0 |
| Langfuse | `langfuse-web`、`langfuse-worker`；依赖 ClickHouse、Valkey、对象存储 | 配置 | MIT / Apache 2.0 / BSD-3 |
| OTel Collector | 网关模式，开启持久化队列 | 配置 | Apache 2.0 |
| Doris | FE、BE | 配置 | Apache 2.0 |
| Apache Airflow | scheduler、api-server、dag-processor、triggerer；任务 Pod | 配置 + DAG | Apache 2.0 |
| Omnigent | `omnigent-server`、runner、host（沙箱中） | 从织境维护的仓库（子仓库）构建；补丁 + 扩展（ADR-0002） | Apache 2.0 |
| agent-sandbox + gVisor / Kata | 控制器；沙箱 Pod | 配置 | Apache 2.0 |
| Envoy Gateway | 控制器 + Envoy 代理 | 配置 | Apache 2.0 |
| PostgreSQL | 高可用集群（CloudNativePG） | 每个组件一个独立 database | PostgreSQL License |
| OpenSearch | 集群 | OM 索引 | Apache 2.0 |
| Jena Fuseki | 服务器 | OM 的 RDF 存储 | Apache 2.0 |
| Valkey | 主从或哨兵 | 缓存 | BSD-3 |
| 对象存储 | 测试环境 OSS；离线 SeaweedFS | S3 兼容接口 | Apache 2.0 |
| JupyterHub（P2） | hub、proxy；用户 Pod | 配置 + 扩展 | BSD |

## 5. 数据归属

| 数据 | 正本存放 |
| --- | --- |
| 本体（对象、关系、属性、映射）、元数据与血缘、指标、分类标签、治理工作流与任务、文章 / 文件 / 记忆 | OpenMetadata |
| 本体实例（对象实例、关系实例） | Doris 本体实例库（每租户一个 database） |
| 取数审计 | AI 网关日志（经 OTel 汇聚）；Doris `audit_log` 补充 SQL 与行数，按 trace_id 关联 |
| 决策轨迹、人工修订、样本 | Langfuse |
| Agent 运行状态（rollout） | PostgreSQL `omnigent`（ADR-0001、0002） |
| 身份、租户、角色、Agent 身份 | Keycloak（Agent 为客户端）；Agent 登记文件在 `config/agents/`，同步到 Keycloak |
| 客户分析数据 | 客户数仓（织境不复制） |

## 6. 关键链路

| 链路 | 路径 |
| --- | --- |
| 用户查询实例 | `web` → `bff`（MCP 客户端，交换令牌）→ AI 网关 → 租户的 MCP Toolbox → Doris；本体定义经公共库 `ontology` 从 OM 读取 |
| Agent 取上下文 | Agent → AI 网关 → OM 内置 MCP / 资产 AI 上下文（OKF v0.2） |
| Agent 查实例与客户数据 | Agent（交换令牌：sub = 人，azp = Agent）→ AI 网关 → MCP Toolbox / 其他数据库 MCP → 数据库 |
| Agent 调模型 | Omnigent / 沙箱 → AI 网关（模型网关）→ 模型 |
| 本体维护 | `web` → `bff` → OM 术语（OM 审批）→ 管线任务生成 Doris 表结构；OM 同步 RDF 到 Fuseki |
| 数据接入 | Airflow → `pipelines`：OM 元数据采集；源系统按本体映射物化到 Doris（直连写入）；飞书定时同步 |
| 决策轨迹 | 各服务、AI 网关与外部平台 → OTel Collector → Langfuse；人工修订由飞书同步管线写回 Langfuse；`bff` 读取展示 |
| 审批 | OM 治理工作流生成任务 → `bff` 展示于审批中心 → 处理结果回写 OM |

## 7. 跨切面机制

| 机制 | 做法 |
| --- | --- |
| 通信 | 浏览器经 `bff`（REST + OpenAPI 3.1）；Agent 取数与取上下文经 MCP；无消息中间件；批处理由 Airflow 编排 |
| 令牌 | Keycloak 登录；Agent 以客户端身份做标准令牌交换（sub = 人，azp = Agent，受众收窄）；无人值守 Agent 用服务账号 |
| 授权 | Phase 1 只到身份、租户、角色与工具一级（AI 网关 CEL 规则）；数据层授权推迟到二期（宪法 IV 例外） |
| 审计 | AI 网关记录每次 MCP 调用；OM 自身记录写操作审计 |
| 多租户 | Keycloak Organization；AI 网关按租户路由到该租户的 MCP Toolbox 实例（只读账号、Doris database 与 workload group）；经 OM 的上下文 Phase 1 不做租户隔离 |
| 可观测 | 公共库注入关联属性（`contracts/otel/attributes.md`），trace 经 MCP `_meta` 传播，经 OTel Collector 汇聚 |

## 8. 待决事项

| # | 事项 | 说明 |
| --- | --- | --- |
| 1 | 系统可观测后端 | 服务指标、日志与基础设施追踪的存储与查看未定；Grafana / Loki / Tempo 为 AGPL-3.0 不可用；候选 Prometheus + Jaeger + OpenSearch Dashboards |
| 2 | OKF v0.2 补丁是否提交上游 | 待定（ADR-0012） |
| 3 | Doris 表结构迁移的评审方式 | 管线按本体生成的迁移以 PR 评审还是以 OM 任务审批 |
| 4 | AI 网关选型 | agentgateway 或 Agent Router，spike 选定（ADR-0013） |
| 5 | 需验证 | ADR-0013 的 5 项 spike；OM MCP 能否接受交换后的令牌；资产 AI 上下文是否包含未审批内容 |
| 6 | 二期 | 数据层授权方向；BI 与 Notebook 的原生 SQL 通道 |
