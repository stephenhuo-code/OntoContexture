# Data Model: 平台技术架构与代码架构基座

本特性的数据模型分两类：**跨切面模型**（所有服务共用，由 `contexture-core` 实现）与**骨架用的最小
领域模型**。业务领域模型由各特性定义。

## 1. 跨切面模型

### RequestContext（请求上下文）

由 `contexture-core.auth` 从委托令牌构建，贯穿一次请求的全部处理。

| 字段 | 类型 | 来源 / 规则 |
| --- | --- | --- |
| `tenant_id` | string | 部署配置常量（Phase 1 单租户，ADR-0007 修订）；不来自令牌 |
| `user_id` | string | 令牌 `sub`；无人值守任务为空 |
| `agent_id` | string? | 令牌 `azp`：经标准令牌交换得到，为 Agent（或 `bff` 等服务）的 Keycloak 客户端（ADR-0013） |
| `agent_owner_id` | string? | 无人值守 Agent 的登记负责人（来自 Agent 登记） |
| `roles` | string[] | 人的角色 |
| `agent_scopes` | string[] | Agent 授权范围（来自 Agent 登记） |
| `data_level_ceiling` | int? | Agent 可访问的最高数据级别（来自 Agent 登记） |
| `token_id` | string | 令牌 `jti`，写入审计 |
| `run_id` / `session_id` | string? | Agent 运行与会话标识（ADR-0001） |
| `trace_id` | string | 当前 OTel trace |

校验规则：令牌验签失败、过期 → 401；受众不符 → 403；均由公共库
统一返回，业务代码不处理。

### CorrelationAttributes（可观测关联属性）

规范见 [contracts/otel/attributes.md](contracts/otel/attributes.md)。每个 span、日志与审计记录都携带，
用于串联轨迹（ADR-0001）。

### 授权（二期）

Phase 1 不做数据层授权（宪法 v1.4.0 原则 IV 例外，ADR-0012）。`agent_scopes`、`data_level_ceiling` 在请求上下文中
预留，二期引入授权求值时使用。

### AuditEvent（审计记录）

JSON Schema 见 [contracts/schemas/audit-event.json](contracts/schemas/audit-event.json)。

| 字段 | 说明 |
| --- | --- |
| `event_id` | 唯一标识 |
| `occurred_at` | 发生时间 |
| `tenant_id`、`user_id`、`agent_id`、`token_id` | 来自 RequestContext |
| `action` | read / write / authz_deny 等 |
| `resource` | 访问的资源（URI 或表 / 列） |
| `decision`、`policy_refs` | 授权结果与依据（二期；Phase 1 可为空） |
| `result_summary` | 返回行数、字段列表等，不含数据内容 |
| `trace_id` | 关联轨迹 |
| `source_service` | 写入方服务 |

来源：AI 网关对每次 MCP 调用记录（经 OTel Collector 汇聚），返回行数与完整 SQL 由 MCP Toolbox / Doris `audit_log`
补齐，按 `trace_id` 关联（research R11）。本 Schema 是统一后的审计记录格式，`source_service` 为 `ai-gateway`。

### ErrorEnvelope（统一错误格式）

JSON Schema 见 [contracts/schemas/error.json](contracts/schemas/error.json)：`code`（稳定的机器可读码）、
`message`（面向人的说明）、`trace_id`、`details`（可选）。

### ServiceCatalogEntry（服务目录项）

架构文档中服务目录的结构化形式：`name`、`domain`、`features`（承载的特性编号）、`owned_stores`、
`interfaces`（REST / MCP / 管线任务）、`depends_on`、`rationale`（拆分理由）。

## 2. 骨架用的最小领域模型

### ObjectTypeRef（对象类型引用）

| 字段 | 说明 |
| --- | --- |
| `type_uri` | `urn:ctx:type:<领域包>:<类型名>`（ADR-0008） |
| `name`、`display_name` | 名称 |
| `version` | 本体版本 |
| `attributes` | 属性列表：`name`、`data_type`、`required`、`data_level` |

骨架中由 `bff` 经 `contexture-core.ontology` 从 OM 读取一个预置且已审批的对象（如“设备”）及其属性（ADR-0008）。

### ObjectInstance（对象实例行）

| 字段 | 说明 |
| --- | --- |
| `object_uri` | `urn:ctx:obj:<tenant_id>:<类型名>:<业务主键>`（保留 `tenant_id` 段，便于将来如需多租户时演进） |
| `type_uri` | 所属对象类型 |
| `attributes` | 属性值 |
| `source` | 数据来源（系统、表） |

骨架在 Doris 本体实例库中预置少量手工数据。

### 取数调用（MCP 工具）

骨架在 MCP Toolbox 中定义一个参数化查询工具（配置在 `deploy/components/mcp-toolbox/config/`，契约在 `contracts/mcp/`）：

| 项 | 内容 |
| --- | --- |
| 工具 | `list_objects`：参数 `type_key`、`limit`（≤ 100）；SQL 模板只查本体实例库中对应的实例表 |
| 调用方 | `bff`（经 `contexture-core.mcp`，以 `bff` 客户端身份交换令牌，受众为 AI 网关） |
| 路由 | AI 网关校验令牌后转发到 Toolbox（Phase 1 单租户，不做租户路由） |
| 结果 | 列与行；超过行数上限时截断并标记 |
| 约束 | Toolbox 使用 Doris 只读账号；超时与行数上限在 Toolbox / Doris 配置；Phase 1 不做数据层授权 |
