# OpenMetadata 能力调研：上下文层、本体与数据治理

2026-10-04 · 依据 OpenMetadata `2.0.3-release` 源码（JSON Schema、Java REST 资源、默认配置、种子数据）、
GitHub 发布说明与官方文档。能力地图见 [OpenMetadata能力地图.svg](../images/OpenMetadata能力地图.svg)。

## 1. 结论摘要

1. **最新版本为 2.0.3（2026-09-30）**，2.1 尚未发布（`main` 为开发线）。架构锁定 2.0.x。
2. **OM 不是全部 Apache 2.0**：Java 服务端（全部 REST API，含 Context Center、向量检索、资产 AI 上下文、
   治理工作流、本体与 RDF）为 Apache 2.0；**内置 MCP 服务模块、OM 界面、Python 采集框架（连接器、剖析、
   数据质量执行器、自动分类）、AI SDK 为 Collate Community License（CCL）**。这直接影响宪法 III 的合规
   判断，见第 6 节。
3. **ADR-0008 的方向可行，但需修正一处**：自定义属性按“实体类型”全局定义（所有术语共用一套字段），不能为
   “设备”“批次”分别定义属性。改为“属性本身也是术语，用自定义关系 `hasAttribute` 挂到对象类型上”，见第 3 节。
4. **OM 没有原生多租户**，Domain 只是软隔离：自定义属性定义、关系类型、工作流、分类是全局的；RDF / SPARQL
   接口只对管理员开放、不按 Domain 过滤。这与 ADR-0007“OM 由织境服务层强制隔离、不对客户开放”一致。
5. **上下文层可复用的比预期多**：Context Center（文章、文件、记忆）、资产 AI 上下文、Persona 上下文、
   混合检索都在 Apache 服务端；但**知识片 LLM 抽取未进入已发布版本**，记忆没有审批与时效。
6. **数据治理层大部分可复用**：分类标签、数据质量、数据契约（ODCS 3.1）、治理工作流（Flowable）、血缘、
   事件订阅、写操作审计均为开源；**列级 / 行级访问控制、读审计、标签沿血缘传播不提供**，与已定的“统一取数
   网关 + iam 审计”一致。
7. **ADR-0006 的待核实项基本落实**：外部 Airflow 编排接口在 2.x 保留且兼容 Airflow 3；外部运行可回写状态；
   开源与收费的 Apps 已区分；自动分类支持中文。

## 2. 许可边界

| 模块 | 许可 | 织境的用法 |
| --- | --- | --- |
| `openmetadata-service`（Java 服务端，全部 REST API） | Apache 2.0 | 作为后端复用 |
| `openmetadata-spec`（JSON Schema） | Apache 2.0 | 复用 |
| `openmetadata-mcp`（内置 MCP 服务） | **CCL 1.0** | 不使用，织境基于 REST 自建 MCP（`context` 服务） |
| `openmetadata-ui` | **CCL 1.0** | 不交付，仅内部使用（ADR-0003） |
| `ingestion/`（Python 采集框架：连接器、剖析、数据质量执行器、自动分类、SDK） | **CCL 1.0** | 复用需宪法例外，见第 6 节 |
| `openmetadata-airflow-apis`（Airflow 插件） | 文件许可为 Apache，源码头为 CCL | 视同 CCL |
| `open-metadata/ai-sdk` | **CCL 1.0** | 不使用 |

CCL 允许使用、修改与再分发，禁止提供与 Collate 竞争的在线服务（SaaS / PaaS）。

## 3. 本体与语义

| 能力 | 接口 | 结论 |
| --- | --- | --- |
| 术语库与术语 | `/v1/glossaries`、`/v1/glossaryTerms`（CRUD、PATCH、`createMany`、版本、软删除与恢复、CSV 导入导出） | 可用；层级为**单父树**（无多继承） |
| 类型化关系 | `POST /v1/glossaryTerms/{id}/relations`、`GET /{id}/relationsGraph`；关系类型 `/v1/system/settings/glossaryTermRelationSettings/relationTypes` | 10 种系统类型（broader / narrower / partOf / hasPart 等），**可自定义关系类型**（带逆关系、RDF 谓词、基数、对称 / 传递标记）；关系类型是全局的；关系本身不能带属性；domain / range 不强制 |
| 审批与版本 | `entityStatus`（Draft / In Review / Approved / Deprecated / Rejected 等）、`reviewers`、种子工作流 `GlossaryTermApprovalWorkflow` | 可用；对已通过术语的每次修改都会重新进入评审，驳回则回滚 |
| 自定义属性 | `PUT /v1/metadata/types/{id}` 定义；`PATCH /extension/<名称>` 赋值 | 36 种实体支持（含术语与**字段**）；**按实体类型全局定义**，不能按某个术语单独定义；类型包括字符串、枚举、实体引用、表格（最多 3 列）等 |
| 字段关联术语 | 表的 PATCH（`source: Glossary`）、`PUT /v1/glossaryTerms/{id}/assets/add` | 可用；标签**不能携带自定义数据**，映射规则需存在字段的自定义属性中 |
| OWL / SKOS 导入 | `PUT /v1/glossaries/name/{name}/importRdf`（2.0） | 可用；`owl:Class` → 术语，`subClassOf` → 父术语，`DatatypeProperty` → 术语的全局自定义属性；不支持 OWL 限制、等价公理与推理 |
| RDF 镜像与 SPARQL | `/v1/rdf/sparql` 等；需开启 Fuseki 并运行重建索引应用 | **Beta、默认关闭、全部接口仅管理员、不按 Domain 过滤**；写入会在重建时丢失，实际只读 |
| SHACL 校验 | — | 2.0.3 未提供（仅在开发线） |
| 新增实体类型 | — | 不支持，需改核心 |
| Metric 实体 | `/v1/metrics` | 有表达式、类型、单位、粒度、维度、度量、过滤条件、关联指标；单位为业务单位，工程单位需用自定义单位 |

**对 ADR-0008 的逐项判断**

| 计划做法 | 判断 | 修正 |
| --- | --- | --- |
| 对象类型与关系类型用术语承载 | 可行 | 单父树足以表达类层级；领域关系用自定义关系类型 |
| 属性模式用术语的自定义属性 | **部分可行** | 自定义属性是所有术语共用的一套字段，不能按类定义属性。**改为：属性也建成术语（术语种类 = 属性），用自定义关系 `hasAttribute` 挂到对象类型上**；“术语种类、数据类型、是否必填、数据级别”作为所有术语共用的自定义属性 |
| 字段映射用字段关联术语 | 调整后可行 | 字段关联到**属性术语**（而非对象类型术语），映射即精确到属性；转换规则、主键等存在字段的自定义属性中 |
| 提案与审批用术语状态和审核人 | 可行 | 每个租户术语库设置自己的审核人 |
| 每租户一个扩展术语库，归属租户 Domain | 部分可行 | 只能软隔离；织境服务层按 Domain 过滤，RDF 只在内部使用（ADR-0007） |

## 4. 上下文层

| 能力 | 接口 | 版本 / 许可 | 结论 |
| --- | --- | --- | --- |
| 文章与快捷链接 | `/v1/contextCenter/pages` | 2.0，Apache | 可复用 |
| 文件（Drive） | `/v1/contextCenter/drive/files`（上传、下载、版本、移动、恢复）、`/drive/folders` | 2.0，Apache | 可复用；**需要 S3 或 Azure 对象存储**；飞书 / Confluence 同步未提供 |
| 知识片抽取 | 上传后异步处理 | 2.0.3 **只做纯文本抽取**；LLM 抽取只在开发线 | 织境自建抽取，结果写入 Memory |
| 记忆（Memory） | `/v1/contextCenter/memories`（列表、创建、版本、置顶、恢复） | 2.0，Apache | 有来源字段（来源类型、来源实体、对话等）、共享范围（私有 / 组织 / 指定人员团队 Domain）、版本；**无审批流程、无时效** → 织境扩展 |
| 资产 AI 上下文 | `GET /v1/{实体类型}/{id}/context`（Markdown 或 JSON，带新鲜度指纹） | 2.0，Apache | 可作为织境 OKF 知识包的输入 |
| Persona 上下文 | `/v1/personas/{id}/aiContext`（规则、预览、编译文档） | 2.0，Apache | 可复用 |
| 语义 / 混合检索 | `POST /v1/search/vector/query`；OpenSearch 混合排序 | Apache | 需开启 LLM 并配置嵌入模型（bedrock、openai、google、本地 djl）；私有化模型能否接入需验证 |
| 内置 MCP 服务 | `/mcp`（Streamable HTTP，无状态；OAuth 或 Bearer 令牌；按调用者权限执行；15 个工具） | **CCL** | 不使用；织境自建 MCP，工具基于同样的 REST 接口 |
| Agent、自动化、对话沉淀记忆、自然语言查询 | — | Collate 专有或未发布 | 不依赖 |
| 变更同步 | `GET /v1/events`（轮询）、`/v1/events/subscriptions`（Webhook，含失败重试与偏移同步） | Apache | 可用于同步到织境的服务 |

## 5. 数据治理与采集编排

| 能力 | 接口 | 许可 | 结论 |
| --- | --- | --- | --- |
| 分类与标签 | `/v1/classifications`、`/v1/tags` | Apache | 可复用 |
| 自动分类（PII） | 采集框架中的 `AutoClassification` 工作流 | **CCL** | 支持中文；基于抽样数据，不扫描文档内容 → 文档级识别织境自建 |
| 数据质量 | `/v1/dataQuality/testDefinitions`、`/testCases`、`/testSuites`、结果与事件接口 | 服务端 Apache，执行器 CCL | 可复用；支持自定义 SQL 测试与外部推送结果，适合承载织境的本体一致性检查（ADR-0006） |
| 数据契约 | `/v1/dataContracts`（校验、结果、ODCS 3.1 导入导出） | Apache | 可复用；结构校验仅部分实体，质量校验仅限表 |
| 治理工作流 | `/v1/governance/workflowDefinitions`、`/workflowInstances`（Flowable） | Apache | 可复用；触发器支持实体事件与定时；工作流定义是全局的 |
| 策略与角色 | `/v1/policies`、`/v1/roles`、`/v1/permissions` | Apache | 只控制 OM 内的实体级操作，**无列级控制**；`hasDomain` 在列表操作依赖搜索后过滤 |
| 血缘 | `/v1/lineage`（表级、字段级）、`/v1/openlineage` | Apache | 可复用 |
| 事件与通知 | `/v1/events/subscriptions` | Apache | 可复用 |
| 审计日志 | `GET /v1/audit/logs` | Apache | **只记录写操作**；读审计由织境 `iam` 负责 |
| 采集管道 | `/v1/services/ingestionPipelines`（部署、触发、状态回写） | Apache | 可复用 |
| 编排客户端 | `AirflowRESTClient`（2.x 保留，兼容 Airflow 3）、`K8sPipelineClient`、`NoopClient` | Apache（Airflow 插件视同 CCL） | 与 ADR-0006 一致 |
| Apps | 开源：搜索索引、Data Insights、AutoPilot、数据契约校验、数据保留、MCP、RDF 索引；Collate：自动化与标签沿血缘传播、AI Agents、数据访问请求等 | — | 不依赖 Collate 应用 |
| 用户、团队、Bot | `/v1/users`、`/v1/teams`、`/v1/bots`；JWT Bot 令牌、个人访问令牌；支持自定义 OIDC（Keycloak） | Apache | 织境服务以 Bot 身份访问 OM |

## 5a. RDF 知识图谱的存储结构（RDF Knowledge Graph Indexing 应用）

| 部分 | 内容 |
| --- | --- |
| 存储 | Apache Jena Fuseki（也支持 QLever）；一个数据集（默认 `openmetadata`），重建时以 `_a` / `_b` 轮换，不停机切换 |
| 命名图 | `graph/ontology`：OM 自身的本体 `openmetadata.ttl`（约 3600 行、75 个类，引入 DCAT、PROV、SKOS）；`graph/shapes`：SHACL 约束 `openmetadata-shapes.ttl`；`graph/knowledge`：全部实体数据的三元组 |
| 转换 | 以 JSON-LD 上下文（base、数据资产、治理、血缘、质量、团队、服务等）把实体 JSON 翻译为三元组；实体 IRI 为 `…/entity/{实体类型}/{uuid}` |
| 同步 | 应用负责全量重建（定时或手动、分批、多线程）；实体变化时实时增量写入 |
| 映射要点 | 术语库 → `skos:ConceptScheme`；术语 → `skos:Concept`；术语关系 → `om:relatedTo`、`om:synonym`、`om:componentOf`、`om:calculatedFrom` 等；自定义属性 → `om:hasExtension`；血缘 → `prov:wasDerivedFrom` |
| 推理 | Jena 推理引擎：RDFS、OWL Lite、OWL DL 与自定义规则 |
| 范围 | 除 AI 图表外的全部实体与实体关系、血缘 |

**用法**：Phase 1 直接开启 OM 的 RDF 能力，由 OM 同步术语库等数据到 Fuseki，用其 SPARQL 接口验证本体
（ADR-0008）。OM 自身的本体以 OWL + SHACL 表达，可作为二期引入逻辑（SHACL）时的参考。

## 5b. 源码核实记录（2.0.3-release，2026-10-07）

| # | 问题 | 结论 | 证据 |
| --- | --- | --- | --- |
| 1 | OM 的本体能力由什么构成 | 术语库 REST 接口（数据在主库）+ 开启后由 OM 自动同步到 Fuseki 的 RDF 知识图谱 | `GlossaryTermResource`、`RdfUpdater` |
| 2 | 本体浏览器从哪里读 | 未选术语库时从主库读（术语、指标 REST）；选中某术语库且开启 RDF 时读 RDF，无数据则回退主库 | UI `useOntologyExplorer.ts` 第 864–884 行 |
| 3 | 术语变化是否实时同步到 RDF | 是，增量写入 | `GlossaryTermRepository` 第 664、703、712、1172 行 |
| 4 | RDF 是否包含自定义属性与自定义关系类型 | 是：自定义属性为 `om:hasExtension` 节点；自定义关系类型按其 RDF 谓词写入 | `RdfPropertyMapper.addExtension`、`RdfRepository` 第 2035–2096 行 |
| 5 | RDF 是否区分草稿与已审批 | 否，`rdf/` 代码未使用审批状态 | 源码检索 |
| 6 | RDF 接口权限 | 全部只对管理员开放（含 SPARQL、图浏览、术语图、导出） | `RdfResource` 各接口调用 `authorizeAdmin` |
| 7 | RDF 是否按域过滤 | 否 | 同上 |
| 8 | 术语 REST 能否按审批状态过滤 | 能：列表接口支持 `entityStatus`、`glossary`、`parent`、`relationTypes`、`q` 等 | `GlossaryTermResource` 查询参数 |
| 9 | 能否向 OM 的数据集写入自有数据 | 不安全：重建时 `CLEAR ALL` 清空整个数据集（含本体与 SHACL 图）；默认 `recreateIndex: true`；启动时只加载 OM 自己的两个本体文件 | `RdfRepository` 第 369 行、`OntologyLoader`、`RdfIndexApp.json` |

未核实：普通 SPARQL 查询是否自动带推理（取决于 `inferenceEnabled`）；SPARQL 与同步的性能。

## 6. 对架构的影响与建议

| # | 影响 | 建议 |
| --- | --- | --- |
| 1 | **Python 采集框架为 CCL**，而 OM 的连接器、剖析、数据质量执行、自动分类都依赖它；宪法 III 规定“源码可用”类许可不得成为交付物硬依赖，例外需架构评审批准并记录 | 新增 ADR 记录 **OM 组件许可边界**：服务端 Apache 照常复用；采集框架作为**经批准的例外**用于私有化交付与内部测试环境（不提供对外在线服务）；MCP 模块、AI SDK 不使用；界面不交付 |
| 2 | ADR-0008 的属性承载方式需修正 | 按第 3 节修正：属性也是术语，用 `hasAttribute` 关系挂到对象类型；字段映射关联到属性术语；共用字段用全局自定义属性 |
| 3 | OM 只能软隔离租户；RDF 接口仅管理员可用 | 维持 ADR-0007：OM 只由织境服务访问并按 Domain 过滤；RDF / SPARQL 只供 `ontology` 等内部服务使用；SHACL 校验在 `ontology` 服务实现 |
| 4 | Context Center 可承载文件、文章与记忆 | 016 文档知识可评估**直接以 OM Context Center 存储文件与知识片**（知识片写为 Memory），`context` 服务负责抽取、审批状态与时效；这会改变 plan 中 `context` 服务“独占文件与知识片存储”的设计，需在 016 的 plan 中决定 |
| 5 | 资产 AI 上下文与 Persona 上下文现成可用 | 017 生成 OKF 知识包时以 `/v1/{实体}/{id}/context` 为输入之一，避免重复拼装元数据上下文 |
| 6 | OM 内置 MCP 为 CCL | 维持“织境自建 MCP”；工具底层调用 OM REST API |
| 7 | 语义检索需嵌入模型 | 004 / 001 部署时配置嵌入服务；私有化模型接入方式需验证（可能需本地 djl 或兼容接口） |
| 8 | 文件上传需对象存储 | 与 research R10 一致（测试环境 OSS，离线 SeaweedFS），需验证 OM 对 S3 兼容存储的支持 |
| 9 | ADR-0006 待核实项 | 第 1–4 项已落实（外部 Airflow 接口保留且兼容 Airflow 3、可回写状态、开源 Apps 清单、自动分类支持中文）；“中文与工业数据的识别效果”仍需实测 |

## 7. 来源

- 源码：<https://github.com/open-metadata/OpenMetadata/tree/2.0.3-release>（`openmetadata-spec`、
  `openmetadata-service/.../resources`、`openmetadata-mcp`、`ingestion/LICENSE`）
- 发布说明：GitHub Releases 2.0.0 至 2.0.3；<https://docs.open-metadata.org/v2.0.x/releases/2.0-release>
- 2.0 治理相关破坏性变更：<https://docs.open-metadata.org/v2.1.x-SNAPSHOT/deployment/upgrade/breaking-changes/data-governance>
- 知识图谱（Beta）：<https://docs.open-metadata.org/v2.1.x-SNAPSHOT/how-to-guides/ontology/knowledge-graph>
- MCP 接入：<https://docs.open-metadata.org/v2.0.x/how-to-guides/mcp/connect>
- AI SDK：<https://github.com/open-metadata/ai-sdk>
- Collate 与 OpenMetadata 对比：<https://www.getcollate.io/comparison>
- Collate 2.0 博客：<https://www.getcollate.io/blog/collate-2-0-ai-for-data-built-on-openmetadata-context-layer>
