# 织境平台技术架构（Phase 1）

2026-10-08 · 依据：宪法 v1.5.0、ADR-0001 至 ADR-0013、`specs/001-engineering-foundation/`

## 1. 架构原则

1. **先把已有框架的能力用好**：OpenMetadata、Keycloak、Langfuse、Airflow、Omnigent、AI 网关、MCP Toolbox 以独立服务集成，按
   “配置 → 扩展 → 补丁”逐级定制（宪法 VI），不额外增加新的能力（ADR-0012）。
2. **只自建框架不具备的能力**：Phase 1 自建服务只有 `bff`（ADR-0013）。
3. **Agent 取数一律经 MCP**：经 AI 网关统一校验令牌、授权、路由与审计，数据库后端用 MCP Toolbox（ADR-0013）。
4. **审批只有一套**：统一使用 OM 治理工作流与任务。
5. **管线可由用户自定义与运维**：数据管线统一在 Airflow 中运行。
6. **架构保持最简**：不引入消息中间件、不建服务网格；Phase 1 只读，数据层授权推迟到二期（宪法 IV 例外）。

## 2. 总览

![织境平台服务架构（Phase 1）](../images/平台服务架构.svg)

文字版：

```text
访问层
  用户浏览器（运行织境 Web 单页应用）          客户数字员工平台 / 客户侧 Agent（Omnigent）
        │ OIDC + PKCE                              │ MCP（交换后的令牌）；OTLP / Webhook 回传轨迹
        ▼                                          ▼
边缘网关（Envoy Gateway）：页面 → web；/bff/* → bff；MCP 与模型 → AI 网关
        │                │                         │                                  │
        ▼                ▼                         ▼                                  ▼
  web（自建，      bff（自建）               AI 网关（MCP 网关 + 模型网关）       OTel Collector
  nginx 提供        ├─ 本体读写、审批 ──► OM    校验令牌、按工具授权、路由、审计          │
  静态资源）        ├─ 决策轨迹 ──► Langfuse ◄────────────────────────────────────────┘
                    ├─ Omnigent 会话代理       ├─► MCP Toolbox（只读账号）──► Doris 本体实例库、客户数据库
                    └─ 页面取数 ──► AI 网关    ├─► OM 内置 MCP
                                               ├─► 其他数据库 MCP 服务（按需）
                                               └─► 模型服务：OpenAI / DeepSeek / 私有化模型（key 只配在网关）

平台底座（第三方服务）
  OpenMetadata  本体（术语库）、元数据与血缘、治理工作流与任务、上下文中心、资产 AI 上下文（OKF v0.2，
                织境补丁）、内置 MCP；RDF 同步到 Fuseki
  Keycloak      身份、角色（一个 realm）；Agent 为客户端，标准令牌交换（sub = 人，azp = Agent）
  AI 网关       agentgateway 或 Agent Router（spike 选定）：MCP 与模型流量的统一入口
  MCP Toolbox   数据库 MCP 服务：参数化查询工具与只读 SQL
  Langfuse      决策轨迹、人工修订、样本数据集
  Airflow       管线编排 ──► pipelines 任务镜像：OM 元数据采集、源系统接入与物化（直连 Doris 写入）、飞书同步
                （含修订写回 Langfuse）、文档解析、治理检查、生成 Doris 表结构
  Omnigent      内部 Agent 运行时（只开放 MCP 工具，Phase 1 不做执行沙箱）；上下文、取数与模型调用经 AI 网关
  存储与基础    PostgreSQL · OpenSearch · Fuseki · Valkey · 对象存储（OSS / SeaweedFS）
```

## 3. 自建部分

| 组件 | 职责 | 承载特性 | 独占存储 | 对外接口 | 主要依赖 |
| --- | --- | --- | --- | --- | --- |
| `web` | 织境 Web 前端（React 单页应用），打包为静态资源镜像，由 nginx 提供；Envoy 把页面请求路由到它（ADR-0003） | 004、008、022 等页面 | — | 静态资源（HTTP） | 浏览器内只调用 `bff` |
| `bff` | 浏览器唯一入口；本体读写；审批待办；轨迹页面；Omnigent 代理；页面取数（经 AI 网关） | 004、010（轨迹页面）、016（本体读写） | Valkey（会话） | REST + SSE（仅浏览器） | OM、Langfuse、Omnigent、AI 网关 |
| `pipelines`（镜像） | Airflow 任务 | 006、015、016、019、020、018 | 不独占（写入各自目标） | Airflow 任务 | Airflow、OM、Langfuse、Doris |
| 公共库 `contexture-core` | 令牌验证与上下文、令牌交换客户端、可观测关联属性、本体读取（`ontology`）、统一错误格式、配置 | 全部 | — | Python 库 | — |
| Paperclip 插件与下发 CLI | 轨迹回传 Langfuse；数字员工下发到 Paperclip | 011、012 | — | Paperclip 插件、CLI | Paperclip、Langfuse |
| 组件配置即代码（`deploy/components/<组件>/config/`） | Keycloak realm 与 Agent 客户端、AI 网关路由与策略、MCP Toolbox 工具定义（含追溯查询模板）、OM 初始化；各带测试 | 002、005、016、021 | — | 配置文件 | — |
| `metric`、`explore`（P2） | 指标生成 SQL；探索与固化 | 007、024、025、026 | 二期确定 | REST / MCP | OM、AI 网关 |

**复用框架、不建服务的特性**：002 身份（Keycloak + 配置即代码）；005 数据访问与审计（AI 网关 + MCP Toolbox；数据层授权推迟）；
014 内部 Agent 运行时（Omnigent）；010 决策轨迹（Langfuse）；006 / 015 / 019 接入（Airflow + OM 采集框架）；016 本体与分级标签
（OM 术语库与分类标签）；017 质量领域包（本体内容）；021 追溯（Toolbox 参数化查询工具）；018 / 009 上下文（OM 上下文中心、
资产 AI 上下文、MCP，OKF v0.2 补丁）；023 / 013 参考 Skill。

## 4. 第三方组件

| 组件 | 部署单元 | 集成方式 | 许可 |
| --- | --- | --- | --- |
| OpenMetadata | `openmetadata-server`、迁移任务；采集任务由 Airflow 拉起 | 从织境维护的 OM 仓库（子仓库）构建、独立部署；Phase 1 补丁仅 OKF v0.2（ADR-0011、0012） | 服务端 Apache 2.0；采集框架与内置 MCP 为 CCL（已批准例外，私有化交付可用）；界面仅内部使用 |
| Keycloak | `keycloak` | 配置（realm 与 Agent 客户端即代码） | Apache 2.0 |
| AI 网关 | agentgateway 或 Agent Router（spike 选定） | 配置（路由、令牌校验、CEL 授权、审计） | Apache 2.0 |
| MCP Toolbox | `toolbox`（一个实例） | 配置（数据源与工具定义） | Apache 2.0 |
| Langfuse | `langfuse-web`、`langfuse-worker`；依赖 ClickHouse、Valkey、对象存储 | 配置 | MIT / Apache 2.0 / BSD-3 |
| OTel Collector | 网关模式，开启持久化队列 | 配置 | Apache 2.0 |
| Doris | FE、BE | 配置 | Apache 2.0 |
| Apache Airflow | scheduler、api-server、dag-processor、triggerer；任务 Pod | 配置 + DAG | Apache 2.0 |
| Omnigent | `omnigent-server`、runner、host（普通 Pod，只开放 MCP 工具） | 从织境维护的仓库（子仓库）构建；补丁 + 扩展（ADR-0002） | Apache 2.0 |
| Envoy Gateway | 控制器 + Envoy 代理 | 配置（页面 → `web`，`/bff/*` → `bff`，MCP 与模型 → AI 网关） | Apache 2.0 |
| nginx | `web` 镜像内的静态资源服务 | 配置 | BSD-2-Clause |
| PostgreSQL | 高可用集群（CloudNativePG） | 每个组件一个独立 database | PostgreSQL License |
| OpenSearch | 集群 | OM 索引 | Apache 2.0 |
| Jena Fuseki | 服务器 | OM 的 RDF 存储 | Apache 2.0 |
| Valkey | 主从或哨兵 | 缓存 | BSD-3 |
| 对象存储 | 测试环境 OSS；离线 SeaweedFS | S3 兼容接口 | Apache 2.0 |
| JupyterHub（P2） | hub、proxy；用户 Pod | 配置 + 扩展 | BSD |

**统一管理**：每个组件在 `deploy/components/<组件>/` 有标准目录：清单 `component.yaml`（版本、镜像来源、许可、
定制级别、负责人）、Chart、各环境参数、配置即代码与测试；CI 检查清单完整、版本锁定、许可合规、镜像进入离线包
（ADR-0009）。

## 5. 数据归属

| 数据 | 正本存放 |
| --- | --- |
| 本体（对象、关系、属性、映射）、元数据与血缘、指标、分类标签、治理工作流与任务、文章 / 文件 / 记忆 | OpenMetadata |
| 本体实例（对象实例、关系实例） | Doris 本体实例库 |
| 取数审计 | AI 网关日志（经 OTel 汇聚）；Doris `audit_log` 补充 SQL 与行数，按 trace_id 关联 |
| 决策轨迹、人工修订、样本 | Langfuse |
| Agent 运行状态（rollout） | PostgreSQL `omnigent`（ADR-0001、0002） |
| 身份、角色、Agent 身份 | Keycloak（Agent 为客户端）；Agent 登记文件在 `agents/<名称>/registration.yaml`，同步到 Keycloak |
| 客户分析数据 | 客户数仓（织境不复制） |

## 6. 关键链路

| 链路 | 路径 |
| --- | --- |
| 用户查询实例 | `web` → `bff`（MCP 客户端，交换令牌）→ AI 网关 → MCP Toolbox → Doris；本体定义经公共库 `ontology` 从 OM 读取 |
| Agent 取上下文 | Agent → AI 网关 → OM 内置 MCP / 资产 AI 上下文（OKF v0.2） |
| Agent 查实例与客户数据 | Agent（交换令牌：sub = 人，azp = Agent）→ AI 网关 → MCP Toolbox / 其他数据库 MCP → 数据库 |
| Agent 调模型 | Omnigent → AI 网关（模型网关）→ 模型 |
| 本体维护 | `web` → `bff` → OM 术语（OM 审批）→ 管线任务生成 Doris 表结构；OM 同步 RDF 到 Fuseki |
| 数据接入 | Airflow → `pipelines`：OM 元数据采集；源系统按本体映射物化到 Doris（直连写入）；飞书定时同步 |
| 决策轨迹 | 各服务、AI 网关与外部平台 → OTel Collector → Langfuse；人工修订由飞书同步管线写回 Langfuse；`bff` 读取展示 |
| 审批 | OM 治理工作流生成任务 → `bff` 展示于审批中心 → 处理结果回写 OM |

## 7. 跨切面机制

| 机制 | 做法 |
| --- | --- |
| 通信 | 浏览器经 `bff`（REST + OpenAPI 3.1）；Agent 取数与取上下文经 MCP；无消息中间件；批处理由 Airflow 编排 |
| 模型接入 | 模型服务（OpenAI、DeepSeek、私有化模型）只在 AI 网关中配置：服务商地址、模型名、key（K8s Secret / KMS）、路由与配额；按人与 Agent 的模型权限和 token 配额用网关自带能力实现（与 LiteLLM 基本对齐，不额外开发）；用量看 Langfuse；Omnigent 以“OpenAI 兼容网关”方式连接 AI 网关，用委托令牌认证，不持有任何厂商 key（ADR-0013） |
| 用户与界面 | 最终用户（业务人员）在 Paperclip 中与数字员工对话；数据处理与治理人员使用织境 Web（重做的 OM 界面，对话能力复用并改造 Omnigent 前端）；默认角色：管理员、AI 工程师、业务用户；织境与 Paperclip 共用同一个 Keycloak realm（ADR-0003、0010） |
| 数字员工平台 | Phase 1 选定 Paperclip（Keycloak 单点登录）：经 MCP 连接 AI 网关；织境以下发 CLI 把数字员工推送到 Paperclip（011）；默认权限按 Keycloak 角色，工具清单写入 Paperclip 工具策略；完整轨迹经 Paperclip 插件回传 Langfuse（012） |
| 外部 Agent 接入 | 不绑定外部框架；客户自建平台经标准 MCP 接入 AI 网关（MCP 授权规范，Keycloak 作授权服务器）；身份分三档：A 每个 Agent 一个客户端、B 平台作为一个客户端（平台内 Agent 为声明属性，注明未验证）、C 服务账号；网关侧必记轨迹，平台侧可选回传（ADR-0010） |
| 令牌 | Keycloak 登录；Agent 以客户端身份做标准令牌交换（sub = 人，azp = Agent，受众收窄）；无人值守 Agent 用服务账号 |
| 授权 | Phase 1 只到身份、角色与工具一级（AI 网关 CEL 规则）；数据层授权推迟到二期（宪法 IV 例外） |
| 审计 | AI 网关记录每次 MCP 调用；OM 自身记录写操作审计 |
| 租户 | Phase 1 单租户：一套环境只服务一个客户，可有多个用户与 Agent；`tenant_id` 作为部署常量写入审计、追踪与日志；多租户设计见 ADR-0007（暂缓，是否采用另行评估） |
| 可观测 | 公共库注入关联属性（`contracts/otel/attributes.md`），trace 经 MCP `_meta` 传播，经 OTel Collector 汇聚 |

## 8. 待决事项

| # | 事项 | 说明 |
| --- | --- | --- |
| 1 | 系统可观测后端 | 服务指标、日志与基础设施追踪的存储与查看未定；Grafana / Loki / Tempo 为 AGPL-3.0 不可用；候选 Prometheus + Jaeger + OpenSearch Dashboards |
| 2 | OKF v0.2 补丁是否提交上游 | 待定（ADR-0012） |
| 3 | Doris 表结构迁移的评审方式 | 管线按本体生成的迁移以 PR 评审还是以 OM 任务审批 |
| 4 | AI 网关选型 | agentgateway 或 Agent Router，spike 选定（ADR-0013） |
| 5 | 需验证 | ADR-0013 的 spike（单租户后为 4 项）；OM MCP 能否接受交换后的令牌；资产 AI 上下文是否包含未审批内容 |
| 6 | 二期 | 数据层授权方向；BI 与 Notebook 的原生 SQL 通道 |
| 7 | 是否多租户 | Phase 1 单租户；是否支持多客户共享实例另行评估，不预设在二期（ADR-0007） |
