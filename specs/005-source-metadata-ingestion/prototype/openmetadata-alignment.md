# 005 原型与 OpenMetadata 能力对齐调研

日期：2026-11-03。用途：原型评审和后续规格编写的依据，**不是正式 spec / plan，也不是集成验收报告**。

2026-11-04 更新：负责人已确认原型，[正式规格](../spec.md) 已编写。负责人同时明确本次暂缓帆软 SQL 血缘解析及写入交付，保留研究，后续另定；下文相关能力分析作为研究保留，不代表 005 的实现承诺。

## 核查基线与结论

- 项目锁定 OpenMetadata `2.0.3`，本地源码提交 `b76076bf43746423d1b07de5957caccf04c57d4b`；以本地 Resource、Schema、Python ingestion 与上游 UI 的接口调用为证据。只阅读上游 UI，不复制实现。
- 同时核对官方 `v2.0.x` 文档。该文档已含 2.0.5 / 2.0.6 内容，不能把新版本的权限说明、交互或修复直接归到项目版本。
- 仓库 Airflow 版本为 `3.3.2`；OM 的 `pipelineServiceClientConfig.enabled` 和 `deployPipelinesConfig.enabled` 仍为 `false`。这证明仓库配置尚未接通编排，不代表已检查运行集群状态。
- 本次没有创建真实数据源、部署 DAG、触发采集或写入真实血缘。以下“有 API”指源码确认，不代表部署已联调通过。
- Agent 按负责人指示暂不做。2026-11-04 确认：国产数据库接入适配及评估均不纳入 005。
- 最新确认：采集管理收进“数据源详情 → 采集任务 → 运行”；不设全局采集运行菜单。帆软解析及独立模块均暂缓，保留调研，后续另行确定。

**规划原则：织境提供操作界面，服务、采集任务、运行状态和血缘尽量以 OM 为正本，任务由独立 Airflow 执行。**

## 1. 数据源接入：流程基本匹配，表单与状态需要进一步对齐

现有“选择连接器 → 连接验证 → 采集范围 → 调度确认”方向与 OM 一致。OM 把连接定义为 `DatabaseService`，把采集配置与调度定义为 `IngestionPipeline`；一个服务可以有多条采集管道。

应保留接入向导，但修正以下细节：

1. **按连接器生成字段。** MySQL / Doris 的 `databaseName` 是 OM 中的目录数据库名称，`databaseSchema` 才可限制物理库；PostgreSQL 有必填 `database` 和 `ingestAllDatabases`；Oracle 通过 `oracleConnectionType` 区分连接方式。不能通用地要求“一个数据库名称 + 一个 TLS 开关”。MES / QMS / ERP 是业务来源，不等同于固定数据库品牌；ERP 的 Oracle 只是现有原型示例。
2. **测试连接是异步任务。** 创建 `testConnection` 类型的 automation workflow、触发执行、轮询结果，展示连接器返回的步骤与成功 / 失败 / 等待状态。测试发生在采集执行环境，BFF 不直接连业务库。
3. **范围使用库 / Schema / 表过滤规则。** OM 已有 include / exclude 与 `useFqnForFiltering`。新连接测试完成不等于表已入 OM；本次未确认有可供通用向导直接调用的“实时枚举任意源库全部表”API。首次采集前先设置过滤规则；采集后可按目录选择对象并生成精确规则。原型现有“测试成功立即展示全部源表”不能原样承诺为 OM 原生功能。
4. **保存服务、保存管道、部署管道、运行要分开。** 保存成功不等于部署成功，部署成功不等于采集成功。已有元数据在暂停调度或新运行失败时仍应可见。
5. **凭证引用是织境的适配设计。** OM 连接 Schema 需要连接参数 / 认证配置，不能把 `ingestion/mes-readonly` 这种任意字符串直接当成原生 API 的完整连接对象。需在技术方案中确定 OM Secrets Manager / 采集端凭证解析，让 BFF 不持有业务库账号秘密。
6. **元数据边界明确关闭采样。** 只启用本次需要的 metadata / lineage；不启用 profiler、sample data、自动分类扫描或数据质量扫描。`extractJsonSchema` 也会采样业务行，005 应明确保持关闭。

主要 API（下文均以 `/api/v1` 为前缀，浏览器仍只调用织境 BFF）：

| 操作 | OM API |
| --- | --- |
| 列出 / 创建 / 更新数据库服务 | `GET / POST / PUT /services/databaseServices` |
| 修改服务属性 | `PATCH /services/databaseServices/{id}` |
| 获取连接测试步骤定义 | `GET /services/testConnectionDefinitions/name/{name}` |
| 创建连接测试任务 | `POST /automations/workflows`，`workflowType=testConnection` |
| 触发 / 查询测试 | `POST /automations/workflows/trigger/{id}`；`GET /automations/workflows/{id}` |
| 创建采集配置 | `POST /services/ingestionPipelines` |

证据：[服务 Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/services/database/DatabaseServiceResource.java)、[测试 Workflow Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/automations/WorkflowResource.java)、[连接 Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/connections/database/)、[采集范围 Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/metadataIngestion/databaseServiceMetadataPipeline.json)、[官方 MySQL 接入流程](https://docs.open-metadata.org/v2.0.x/connectors/database/mysql)。

## 2. 采集运行：OM 原生已有，应复用

OM UI 的 `IngestionListTable` 已展示任务类型、数量、调度和最近运行，并调用部署、触发、启停与日志 API。状态 Schema 明确包含 `queued / running / success / partialSuccess / failed / stopped`，部分成功不是织境需要发明的新状态。

建议布局：

- 数据源详情提供“采集任务”标签，列出该服务的 metadata / lineage 管道。
- 每条任务单独拥有计划、启停、部署状态和运行历史；不要把一个服务永久简化为一个定时任务。
- 不设全局“采集运行”入口。运行记录、日志、触发与暂停 / 恢复收进当前数据源的具体采集任务，不建立第二套运行状态库。
- 运行详情展示真实的阶段、成功 / 失败 / 跳过数量、错误摘要和日志；不能固定画出每个连接器都有相同的四个阶段。
- “重试”默认触发新的一次运行，不宣称只重跑失败的表或具备断点续跑。

| 操作 | OM API |
| --- | --- |
| 列表及按服务过滤 | `GET /services/ingestionPipelines?service={serviceFQN}` |
| 部署 | `POST /services/ingestionPipelines/deploy/{id}` |
| 触发 | `POST /services/ingestionPipelines/trigger/{id}` |
| 暂停 / 恢复调度 | `POST /services/ingestionPipelines/toggleIngestion/{id}` |
| 运行历史 / 单次运行 | `GET /services/ingestionPipelines/{fqn}/pipelineStatus`；`GET /services/ingestionPipelines/{fqn}/pipelineStatus/{runId}` |
| 最新日志 | `GET /services/ingestionPipelines/logs/{id}/last` |
| 外部运行状态写回 | `PUT /services/ingestionPipelines/{fqn}/pipelineStatus` |

**独立 Airflow 的优先方案**：在现有 Airflow 安装与 OM 版本匹配的 `openmetadata-ingestion` 和 `openmetadata-managed-apis`，配置 OM `AirflowRESTClient` 指向它。源码中有 Airflow 3 的插件路由探测，依赖配置也列出 Airflow 3.3.2，说明该路径有代码支持；仍须实测插件鉴权、DAG 文件共享 / 分发、KubernetesExecutor 任务镜像和日志回传。

如果改成完全外部维护的 DAG，执行 ingestion 和写回状态仍可行，但不能默认 OM 的部署 / 启停 API 能管理任意外部 DAG。尤其要明确 **OM 动态生成采集 DAG** 与 **仓库 PR 管理自定义 DAG** 的归属，避免两个地方同时修改同一份任务定义；这需在 005 plan 中明确，并视结果补充 ADR-0006。

证据：[管道 Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/services/ingestionpipelines/IngestionPipelineResource.java)、[管道 Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/ingestionPipelines/ingestionPipeline.json)、[AirflowRESTClient](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/clients/pipeline/airflow/AirflowRESTClient.java)、[当前部署配置](../../../deploy/components/openmetadata/values/base.yaml)、[官方独立 Airflow 接入](https://docs.open-metadata.org/v2.0.x/deployment/ingestion/openmetadata)。

## 3. 报表血缘：OM 有模型、API 与展示，帆软需要适配

本地 ingestion/dashboard 连接器目录、连接 Schema 和官方支持列表中未找到 FineReport / 帆软连接器。不能把“支持 BI 血缘”解释成“帆软可直接开箱接入”。

OM 已有：

- `DashboardService`：BI 服务；`Dashboard`：报表 / 看板；`Chart`：图表。
- `DashboardDataModel`：数据集模型，带 `sql` 与 `columns` 字段。
- `CustomDashboard`：自定义连接器的官方扩展入口。
- 血缘边的 `sqlQuery`、`columnsLineage`、`pipeline`、`source` 等属性；表、数据集、报表可以统一进入血缘图。

建议采用的建模（需用帆软实际报表结构验证）：

```text
源表 / 视图 → 帆软数据集（DashboardDataModel）→ 报表（Dashboard）
                  ↑
          SQL、输出字段与映射证据
```

**补充的工作**：通过帆软可用的导出 / 接口取得报表、数据集、连接信息与 SQL；解析 SQL，关联已采集实体，生成上述实体与边。普通 `SELECT` 没有目标表，不能只调用“按 SQL 建表间血缘”就认为报表身份和数据集身份也自动创建了。动态参数、无法解析的 SQL 和未匹配来源需单独列出，不能猜出一条关系。

**最新范围决定（2026-11-04）**：负责人明确本次暂缓帆软 SQL 解析及血缘写入交付，保留调研结论，后续另行确定。独立模块也不设计；原型已移除菜单、页面、SQL 编辑 / 解析 / 发布操作及其他页面的跳转入口。上述能力分析仅作为后续评估依据，不作为 005 的实现或验收要求，也不自动归入其他特性编号。

| 操作 | OM API |
| --- | --- |
| BI 服务 | `/services/dashboardServices` |
| 报表 / 图表 / 数据集实体 | `/dashboards`、`/charts`、`/dashboard/datamodels` |
| 读取血缘 | `GET /lineage/{entity}/{id}`，支持上下游深度参数 |
| 写入表级 / 字段级血缘 | `PUT /lineage`，实体引用 + 可选 `lineageDetails.columnsLineage` |

数据库的血缘采集也有能力差异：本地 Doris 连接 Schema 声明视图血缘能力，不能自动推定拥有与 MySQL / PostgreSQL 完全相同的查询日志血缘流程。

证据：[DashboardDataModel Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/dashboardDataModel.json)、[Dashboard Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/dashboard.json)、[CustomDashboard 扩展配置](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/connections/dashboard/customDashboardConnection.json)、[Dashboard 采集拓扑](../../../third_party/openmetadata/src/ingestion/src/metadata/ingestion/source/dashboard/dashboard_service.py)、[血缘 Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/lineage/LineageResource.java)、[官方 BI 连接器列表](https://docs.open-metadata.org/v2.0.x/connectors/dashboard)、[官方血缘图交互](https://docs.open-metadata.org/v2.0.x/how-to-guides/data-lineage/explore)。

## 4. 数据治理：OM 有完整能力，不能与“采集运行”混为一个模块

本地上游默认导航中：

- **Govern**：Glossary、Ontology Explorer、Classification、Metrics、Column Bulk Operations、Workflows。
- **Observability**：Data Quality、Incident Manager、Alerts、Test Library。
- **Data Marketplace**：Domains、Data Products。
- **资产详情**：负责人、业务域、标签 / 术语、描述、版本、任务与讨论等。

这些功能存在于源码 / API，并不代表全部都应进入 005；是否显示还受部署配置、权限与扩展影响。

| 治理能力 | 可复用的 OM API | 织境规划位置 |
| --- | --- | --- |
| 术语与业务知识 | `/glossaries`、`/glossaryTerms` | 沿用整体原型“数据治理 → 术语库”，本体细化在 016 |
| 分类分级 | `/classifications`、`/tags` | “数据治理 → 标签 / 分类分级”，按 016 范围推进 |
| 域与数据产品 | `/domains`、`/dataProducts` | 资产归属与治理组织维度，明确后续范围后再开放 |
| 治理工作流 | `/governance/workflowDefinitions` 等 | 待办汇总进 008 审批中心，治理运维按 025 推进 |
| 数据质量 | `/dataQuality/testSuites`、`/dataQuality/testCases` 等 | 025；不混入 005 的只采集元数据范围 |

**005 的安排**：保留整体导航规划中的治理位置，资产与字段展示已存在的治理属性；不在本次造完整的术语管理、标签管理和质量检查系统，也不为了填满菜单新建空功能页。当前原型优先补数据源目录，治理页面位置在整体导航评审中确认。

证据：[OM 默认侧栏定义](../../../third_party/openmetadata/src/openmetadata-ui/src/main/resources/ui/src/constants/LeftSidebar.constants.ts)、[官方治理介绍](https://docs.open-metadata.org/v2.0.x/how-to-guides/data-governance)、[ADR-0006](../../../docs/adr/0006-三域数据治理与管线编排.md)、[阶段开发计划](../../../docs/Phase1-特性列表与开发计划.md)。

## 5. 数据源多层目录：按 OM 实体层级，已补原型

```text
数据源服务 mock-qms
└─ 数据库 qms
   └─ Schema public
      ├─ inspection_record
      ├─ inspection_value
      └─ ncr
         └─ 字段在右侧详情中展示
```

MySQL / Doris 在本版本连接器中通常用 `databaseName` 或默认 `default` 作为 OM Database，物理库进入 DatabaseSchema。原型据此展示 `mock-mes → default → mes → 表`、`mock-dw → default → mock_dw → 表`，不能为了看起来简洁就把这两层混掉。生产必须以实际返回的实体关系为准，不从连接器名称硬编码层级。

| 目录级别 | OM 查询 |
| --- | --- |
| 服务 | `GET /services/databaseServices` |
| 数据库 | `GET /databases?service={serviceFQN}` |
| Schema | `GET /databaseSchemas?database={databaseFQN}` |
| 表 | `GET /tables?databaseSchema={schemaFQN}` |
| 字段 | `GET /tables/{id}` 返回的 `columns` |

生产交互按需加载、分页，节点保存实体 ID / 类型 / FQN；选中数据库或 Schema 展示其子项，选中表展示字段。目录反映**已采集元数据**，不是源库实时浏览器；首次采集未完成显示“未采集”，不能用空目录断言源库无表。

当前离线原型已加入上述四层展开、选择、面包屑和表字段联动，移动窗口提供“目录”按钮。演示每个示例源的一条库 / Schema 分支，不表示一个服务只能有一个数据库。

证据：[Database Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/databases/DatabaseResource.java)、[DatabaseSchema Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/databases/DatabaseSchemaResource.java)、[Table Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/databases/TableResource.java)、[通用连接器目录映射](../../../third_party/openmetadata/src/ingestion/src/metadata/ingestion/source/database/common_db_source.py)。

## 6. 数据源标签与业务域：2026-11-03 补充核查

本节以同一锁定提交的 `DatabaseService` 为对象；“OM 支持的字段”“原生界面入口”和“005 是否采用”分别判断。未查询运行实例的标签 / 业务域清单，以下内置项来自源码初始化定义，不能视为当前部署的实际清单。

| 属性 | OM 的含义与存储 | 原生数据源界面 |
| --- | --- | --- |
| 分类标签 | `tags[]`，`source=Classification`；引用已有分类下的标签 | 服务详情侧栏可以维护 |
| 业务术语 | 同在 `tags[]`，但 `source=Glossary`，引用术语库中的术语 | 服务详情侧栏单独维护术语 |
| 重要程度 Tier | 分类标签的一种，内置 `Tier.Tier1` 至 `Tier.Tier5` | 服务详情头部单独维护；不能当作敏感级别 |
| 业务域 Domain | 独立的 `domains` 字段；创建 API 接收已有域的 FQN 数组 | 服务详情头部维护，不是新建连接的必填项 |
| 负责人 | `owners`，引用用户 / 团队 | 服务详情头部维护 |
| 数据产品 | 独立的 `dataProducts` 关联 | 服务详情侧栏维护；不是业务域或标签 |

证据：[创建服务契约](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/api/services/createDatabaseService.json)、[标签类型](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/type/tagLabel.json)、[服务详情头部](../../../third_party/openmetadata/src/openmetadata-ui/src/main/resources/ui/src/pages/ServiceDetailsPage/ServiceDetailsPage.tsx)、[服务详情侧栏](../../../third_party/openmetadata/src/openmetadata-ui/src/main/resources/ui/src/pages/ServiceDetailsPage/ServiceMainTabContent.tsx)。

源码内置分类包括：`Tier`（Tier1—Tier5）、`PII`（None / NonSensitive / Sensitive）、`PersonalData`（Personal / SpecialCategory）、`Certification`（Bronze / Silver / Gold）、`KnowledgeCenter`（Article / QuickLink / HowToGuide）。这是全平台的分类初始化定义，不是“新建数据库服务必须填写的五类字段”，也不表示它们都适合标注数据库服务。实际可选标签应读取 OM，不能写死；用户也可维护自己的分类与标签。项目 `tools/seed.py` 另有“数据级别”分类初始化逻辑，属于织境示例配置，不能称为 OM 内置分类。

证据：[分类初始化定义](../../../third_party/openmetadata/src/openmetadata-service/src/main/resources/json/data/tags/)、[项目种子脚本](../../../tools/seed.py)、[官方分类说明](https://docs.open-metadata.org/v2.0.x/how-to-guides/data-governance/classification)。

业务域的来源与影响：

- 域是单独创建和维护的实体。`GET /api/v1/domains` 查询，`POST /api/v1/domains` 创建；不是从连接器类型自动生成。创建服务时，后端会把 `domains` 中的 FQN 解析为已存在的 Domain 实体。
- `createDatabaseService` 契约只将 `name`、`serviceType` 列为必填字段，业务域可不提供。原生 `AddServicePage` 的名称卡片只有名称和可选描述，没有业务域、标签或术语选择器；已有服务的详情页才提供这些治理属性的维护入口。API 允许创建时传入，不代表原生新建界面也提供相应输入。
- Database 未设域时继承服务的域；Schema 未设域时继承 Database 的域；Table 未设域时继承父级的域。因此给整个数据源指定域会影响下级资产的默认归属，不能当作无影响的展示标签。
- 原型写死的 `MES / QMS / ERP / 数仓` 没有 OM 域实体来源，也不是 OM 内置业务域。这些名称不能未经用户定义就充当 Domain；即使将来同名建域，也必须引用实际域实体。

证据：[域 Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/domains/DomainResource.java)、[域引用校验 `validateDomains`](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/EntityRepository.java)、[新建服务名称卡片](../../../third_party/openmetadata/src/openmetadata-ui/src/main/resources/ui/src/components/Settings/Services/AddService/ServiceNameCard/ServiceNameCard.tsx)、[Database 域继承](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/database.json)、[Schema 域继承](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/databaseSchema.json)、[Table 域继承](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/table.json)。

**负责人已确认：配置向导去掉业务域；每个数据源的属性与 OM 对齐并支持用户配置。** HTML 已移除向导中的域字段及 MES / QMS / ERP / 数仓硬编码域值；在每个数据源的概览增加“数据源属性 → 编辑属性”。初始示例均未分配治理属性，不自动从源系统名称推导归属。

属性编辑包括显示名称、描述、负责人、业务域、Tier、分类标签、业务术语与数据产品；服务标识和连接器在属性编辑中只读，连接参数仍通过连接配置向导维护。显示名称留空时使用服务标识。支持保存、取消、移除关联；修改连接配置不会覆盖已保存的治理属性。`Tier` 与分类标签使用 `source=Classification` 的 `tags`，术语使用 `source=Glossary` 的 `tags`，不另造语义字段。HTML 内部原有 `name` / `service` 分别对应 OM `displayName` / `name`；此演示状态不是可直接提交的 OM 请求体。

补充核查发现：虽然 `domains` 契约是数组，OM 默认实体规则禁止数据库服务拥有多个域；负责人默认允许多名用户或一个团队；数据产品必须与资产的域匹配。原型据此使用域单选、负责人类型切换及产品归属校验。Tier 单选，PII / PersonalData 按初始化定义互斥；取消勾选可以清空。生产须读取实际启用的实体规则与分类定义，不能把默认规则当作不可配置的底座限制。

证据：[OM 默认实体规则](../../../third_party/openmetadata/src/openmetadata-service/src/main/resources/json/data/settings/entityRulesSettings.json)、[UI 规则解析](../../../third_party/openmetadata/src/openmetadata-ui/src/main/resources/ui/src/utils/RuleEnforcementUtils.ts)、[后端产品域校验](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/EntityRepository.java)。

离线原型的人员、域、术语和数据产品使用明确标注的“示例”目录，仅用于验证选择 / 取消 / 校验交互，不代表企业实际定义或部署状态。分类标签演示 PII / PersonalData，Tier 单独展示，不代表服务仅支持这些分类。生产选项需经 BFF 查询 OM 的 `/users`、`/teams`、`/domains`、`/classifications`、`/tags`、`/glossaryTerms`、`/dataProducts`，处理权限、分页和空目录；没有可选实体时显示空状态，不自动创建。本次未增加域、术语、标签或产品的管理模块。

## 7. 数据库、Schema、表与字段属性：原型已补齐本轮范围

负责人要求将数据源下级资产的属性也与 OM 对齐。原型在数据库 / Schema 目录页和表详情增加属性卡片及编辑入口，在字段行增加属性编辑；修改按源、层级、完整名称隔离，保留独立的元数据修改状态，不改源结构定义。目录与表选择器同步显示用户设置的显示名称，原名称和 FQN 继续保留；Database 名称可能是 OM 逻辑目录名称，不一概称为源库物理名称。

| 层级 | 本轮可编辑属性 | 只读信息 |
| --- | --- | --- |
| Database / DatabaseSchema / Table | `displayName`、`description`、`owners`、`domains`、`tags`（分类 / 术语 / Tier）、`dataProducts`、`retentionPeriod` | 名称、FQN、所属层级；表类型、字段数、已知表约束 |
| Table.columns 中的字段 | `displayName`、`description`、`tags`（分类 / 术语） | 名称、FQN、类型、主键 / 唯一键成员标识 |

字段 Schema 没有独立的 `owners`、`domains`、`dataProducts`，因此字段编辑不照搬资产级表单。Tier 在本轮作为资产级独立控件，不额外增加字段级 Tier 控件。保留周期是 ISO 8601 时长元数据，不触发删除、清理或源库配置变更。普通表与主键 / 唯一键来自现有 mockfactory 建表定义；Doris 的 `UNIQUE KEY` 展示为 UNIQUE / UK，不误标为物理主键。当前示例没有外键、分区、视图定义，明确显示未提供，不从字段名称猜测关联。

**继承按锁定版本 Repository 实现核查，不假定所有治理属性统一向下继承：**

| 属性 | 原型采用的读取行为 |
| --- | --- |
| 业务域 | Database 未单独设置时继承 Service；Schema 继承 Database；Table 继承 Schema |
| 负责人 | Database 不从 Service 继承；Schema 未设置时继承 Database；Table 未设置时继承 Schema |
| 保留周期 | Schema 未设置时继承 Database；Table 未设置时继承 Schema；Database 单独设置 |
| 标签 / 术语 / Tier / 数据产品 | 本轮不模拟为上述层级的自动继承；不将服务标签复制到全部表或字段 |

展示区标注“单独设置”或“继承自 + 来源实体完整名称”。业务域选择“继承上级”、负责人取消全部选择、保留周期留空时，恢复相应继承；上级也未设置时显示未分配 / 未设置。父级修改后下级继承值随之变化，子级的单独设置不被覆盖。数据产品选择按当前有效域（含继承域）校验；父级修改造成子级既有产品与域不匹配时提示调整，不偷偷改写产品。该提示是原型的处理设计，真实 OM 更新传播、校验及冲突响应须在集成中验证。

证据：[Database Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/database.json)、[DatabaseSchema Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/databaseSchema.json)、[Table / Column Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/data/table.json)、[基础继承方法](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/EntityRepository.java)、[DatabaseRepository](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/DatabaseRepository.java)、[DatabaseSchemaRepository.applyInheritance](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/DatabaseSchemaRepository.java)、[TableRepository.applyInheritance](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/TableRepository.java)、[模拟源建表定义](../../../testdata/mockfactory/schema/base.py)。

正式适配使用 `/api/v1/databases/{id}`、`/databaseSchemas/{id}`、`/tables/{id}` 的 GET / PATCH。字段属性通过所属 Table 的 `columns` 修改，不设计不存在的独立字段实体写接口。生产需先按字段 FQN 定位当前列结构，避免使用过期数组下标，并处理并发修改、嵌套列、权限、OM 实体规则及服务端派生标签；本轮离线原型只演示现有平铺字段样例，不宣称这些已联调。

证据：[Database Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/databases/DatabaseResource.java)、[DatabaseSchema Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/databases/DatabaseSchemaResource.java)、[Table Resource](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/resources/databases/TableResource.java)。

本轮补齐的是已讨论的元数据属性和编辑交互，不等于复制全部 OM 功能。认证、生命周期、自定义属性定义、剖析、质量测试、样例数据和使用统计等仍不在本轮界面范围；不得因 Schema 中存在字段就自动增加模块。

## 8. 采集配置归属层级与资产详情拆分

2026-11-03 核查：数据库元数据采集的配置归属是 **DatabaseService 下的 IngestionPipeline**，不能等同于目录里的 Database 对象。`IngestionPipeline.service` 关联服务，`sourceConfig` 保存采集范围和行为，`airflowConfig` 保存调度等执行配置；任务 FQN 也由服务 FQN 与任务名组成。一个服务可以有多条任务。

| 内容 | 所在位置 / 生效范围 |
| --- | --- |
| 连接器、地址、连接参数 | DatabaseService 的 connection |
| 元数据采集范围、行为 | IngestionPipeline.sourceConfig；可通过 databaseFilterPattern / schemaFilterPattern / tableFilterPattern 限定库、Schema 与表，支持 useFqnForFiltering |
| 调度、部署、运行、日志 | IngestionPipeline；从所属数据源详情进入具体任务 |
| 数据库 / Schema / 表 / 字段 | 被采集的元数据资产；不因有范围过滤就各自拥有一套采集调度 |

连接器还可能限制可访问范围。例如锁定版本 Postgres 的 `database` 是初始连接数据库，默认只读取该库；启用 `ingestAllDatabases` 后可以发现其他数据库，再应用过滤规则。MySQL / Doris 的 `databaseName` 是 OM 逻辑目录名，`databaseSchema` 才是物理库范围相关配置。因此“本示例每个连接只配置一个库”不能推导为“OM 的采集任务只支持数据库级”。

证据：[IngestionPipeline Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/ingestionPipelines/ingestionPipeline.json)、[任务归属与 FQN 实现](../../../third_party/openmetadata/src/openmetadata-service/src/main/java/org/openmetadata/service/jdbi3/IngestionPipelineRepository.java)、[数据库元数据采集配置](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/metadataIngestion/databaseServiceMetadataPipeline.json)、[Postgres 连接 Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/connections/database/postgresConnection.json)、[MySQL 连接 Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/connections/database/mysqlConnection.json)、[Doris 连接 Schema](../../../third_party/openmetadata/src/openmetadata-spec/src/main/resources/json/schema/entity/services/connections/database/dorisConnection.json)、[官方 PostgreSQL 流程](https://docs.open-metadata.org/v2.0.x/connectors/database/postgres)。官方 v2.0.x 是滚动文档，项目行为以锁定源码为准。本结论针对 005 的元数据采集，不扩展为所有剖析、测试或其他类型任务均无资产级配置。

**原型已按负责人反馈拆分页面：**

- 数据源详情保留连接配置、采集配置、采集任务及运行；其“已采集元数据”页签展示数据库目录入口。
- 选中数据库 / Schema / 表后进入该资产自己的详情，以资产名称和 FQN 为标题；不再沿用数据源的名称、部分成功状态、连接配置按钮和采集页签。
- 下级详情保留属性、子目录、结构与字段编辑，通过面包屑或“返回所属数据源”回到源服务；不新增独立同步任务或重复运行记录。
- 资产层级面包屑只显示到当前层级，选中数据库不再显示下级 Schema 为当前位置。

原型的连接器差异字段、首次范围过滤向导及真实任务部署依然是此前记录的待对齐项；本轮解决管理归属与展示层级，没有声称完成这些后端适配。

## 当前原型与后续工作

1. 已完成：多层目录；Agent 暂不做；无国产库产品页面。
2. 已完成：采集管理按“数据源详情 → 采集任务 → 运行”组织。原型每个已配置源演示一条元数据采集任务；运行按源 / 任务范围显示，支持日志、筛选、手动触发、暂停 / 恢复和修复后重试，不设全局运行入口。
3. 已完成：移除帆软 SQL 血缘独立页面及所有操作入口；按 2026-11-04 确认，本期解析及写入交付也暂缓，保留研究，后续另行确定。
   已补充：数据源以及数据库 / Schema / 表 / 字段的本轮属性交互，详见第 6、7 节。
4. 待后续对齐：保留接入向导，按连接器配置字段、异步测试、范围过滤、保存 / 部署 / 运行状态修正。
5. 待后续明确：治理导航与后续特性衔接，不把完整治理能力塞进 005。

原型已确认并据此编写正式 spec；本研究与原型不构成集成验收，尚未开始生产实现。
