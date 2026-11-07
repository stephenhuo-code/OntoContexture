# Data Model: 源系统元数据采集（005）

**原则**：宪法 VII——零新增持久化实体。全部事实正本在 OpenMetadata 2.0.3（以及 Airflow 的调度状态）；BFF 只做接口 DTO
与运行内投影（契约见 [contracts/openapi.yaml](contracts/openapi.yaml)），不新增数据库表。BFF 本地存储仍只有 002 的 `bff_sessions`。

## 1. 正本实体（OpenMetadata 原生）

| 织境概念 | OM 实体 | 关键字段（本期使用） | 说明 |
| --- | --- | --- | --- |
| 数据源 | `DatabaseService` | `name`（服务标识）、`displayName`、`serviceType`、`connection.config`、`description`、`owners`、`domains`、`tags`、`dataProducts` | 连接字段按连接器映射，见 research R9；密码经 OM SecretsManager 加密，用户令牌读取时为 `*********` |
| 元数据采集任务 | `IngestionPipeline`（`pipelineType=metadata`） | `name`、`fullyQualifiedName`、`sourceConfig.config`（`DatabaseMetadata`：三级过滤、`includeViews`、`markDeletedTables=false`、`overrideMetadata=false`）、`airflowConfig.scheduleInterval`、`airflowConfig.pipelineTimezone=Asia/Shanghai`、`enabled`、`deployed` | 每个已配置数据源恰好一条 |
| 视图血缘任务 | `IngestionPipeline`（`pipelineType=lineage`） | `sourceConfig.config`（`DatabaseLineage`：`processViewLineage=true`、`processQueryLineage=false`、`processStoredProcedureLineage=false`）、调度同上 | 每个数据源 0 或 1 条；仅在 `includeViews=true` 时存在 |
| 运行记录 | `PipelineStatus` | `runId`、`pipelineState`、`startDate`、`endDate`、`status[]`（StepSummary） | 由 Airflow 中运行的 OM 采集框架回写，BFF 只读 |
| 测试连接 | `Workflow`（automations，`workflowType=TEST_CONNECTION`） | `request`、`status`、`response.steps[]` | 临时实体，结果读取后由 BFF 删除 |
| 数据库 / Schema | `Database`、`DatabaseSchema` | `name`、`fullyQualifiedName`、`displayName`、`description`、`owners`、`domains`、`tags`、`dataProducts`、`retentionPeriod` | MySQL / Doris 的 Database 为 `default`，物理库为 Schema |
| 表 / 视图 | `Table` | `tableType`、`tableConstraints`、`schemaDefinition`、`columns[]`（`name`、`dataTypeDisplay`、`constraint`、`displayName`、`description`、`tags`）及治理字段 | Doris 键列的 `constraint=PRIMARY_KEY`（原生连接器） |
| 视图血缘 | `Lineage` 边 | `fromEntity`、`toEntity`、`lineageDetails.columnsLineage` | 由 lineage 任务写入 |
| 治理选项 | `User`、`Team`、`Domain`、`DataProduct`、`Classification`、`Tag`、`Glossary`、`GlossaryTerm` | 名称、FQN、`mutuallyExclusive`、数据产品所属域 | 只读；本期不创建治理实体 |

## 2. 身份与权限（配置，不是新实体）

| 位置 | 内容 |
| --- | --- |
| Keycloak `contexture-bff` 客户端 | 增加受众 `contexture-openmetadata`（令牌交换目标）；增加把 realm 角色写入扁平声明的 mapper |
| OM `authenticationConfiguration.jwtTeamClaimMapping` | 指向上述声明，按值入组 |
| OM 团队 / 角色 / 策略（`tools/om_config.py` 幂等创建） | 团队 `admin`、`ai-engineer`；角色授予 DatabaseService、IngestionPipeline、Workflow（测试连接）与 Database / Schema / Table 治理属性所需操作 |
| Airflow 用户 | 供 OM `AirflowRESTClient` 使用，密码来自 `om-secrets/airflow-password` |

## 3. BFF 投影（运行内计算，不持久化）

| 投影 | 来源 | 规则 |
| --- | --- | --- |
| `SourceSummary.tableCount` / `columnCount` | OM `tables?service=<name>&fields=columns`（分页） | 计数含视图；无数据时为 0，不补造 |
| 任务 `kind` | `pipelineType` | `metadata` / `lineage`；其他类型（如 profiler）不显示 |
| 数据源状态（列表“最近采集”） | 元数据采集任务最近一次 `pipelineState`；无任务为“待配置”，有任务无运行为“待首次采集” | “需要关注”= 任一任务最近一次为 `partialSuccess` 或 `failed` |
| “调度已暂停” | 任一有 cron 的任务 `enabled=false` | |
| 运行步骤统计 | `PipelineStatus.status[]` | 原样映射；不合成四阶段 |
| 继承来源 | 上级实体的 `domains` / `owners` / `retentionPeriod` 与本级是否 `inherited` | 规则：域 服务→库→Schema→表；负责人与保留周期 库→Schema→表（spec FR-007） |

## 4. 状态与生命周期

- **数据源**：未保存 → 已保存（仅有 `DatabaseService`）→ 已配置（有元数据采集任务且已部署）。部署失败时实体保留、`deployed=false`，界面显示真实错误，用户再次保存重试部署。
- **视图血缘任务**：随“采集视图 + 创建视图血缘任务”创建；关闭任一项保存时删除该任务及其运行记录（OM 删除管道的原生行为）。
- **运行**：`queued → running → success | partialSuccess | failed | stopped`，全部由 OM 回写；同一任务存在 `queued` / `running` 时拒绝再次触发（BFF 先读 OM 状态校验，Airflow DAG `maxActiveRuns=1` 兜底）。
- **测试连接**：`Pending → Running → Successful | Failed`；参数变更后前端丢弃旧结果。

## 5. 校验规则（来自 spec）

| 规则 | 位置 |
| --- | --- |
| 服务标识 `^[a-z][a-z0-9-]{1,49}$`，唯一；已有采集结果后服务标识与连接器只读 | BFF + 前端 |
| 库字段按连接器必填 / 选填（research R9） | BFF + 前端 |
| 过滤规则必须是合法正则 | BFF（以 OM 采集框架使用的 Python `re` 语义校验）+ 前端提示 |
| `createLineageTask=true` 要求 `includeViews=true` | BFF |
| 采样、剖析、软删除恒为关闭 | BFF 固定写入，不接受请求覆盖 |
| 数据产品所属域与有效业务域一致；同一互斥分类单选；保留周期为 ISO 8601 时长 | BFF（并依赖 OM 自身校验） |
| 字段只可改显示名称、描述、分类标签、业务术语 | BFF |
