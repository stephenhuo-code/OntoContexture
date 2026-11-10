# 006 原型与 OpenMetadata 搜索能力对齐调研

- 调研日期：2026-11-09
- 用途：原型评审和后续规格编写的依据，**不是正式 spec / plan，也不是集成验收报告**。
- 依据：项目锁定的 OpenMetadata 源码 `third_party/openmetadata/src`（上游 `2.0.3-release`，提交 `b76076bf`），本仓库部署配置，以及本地集群只读核查。
- 架构图：[om-search-architecture.svg](om-search-architecture.svg)；页面结构方案：[page-structure.md](page-structure.md)
- 下文路径缩写：
  - `$OM` = `third_party/openmetadata/src`
  - `$SVC` = `$OM/openmetadata-service/src/main/java/org/openmetadata/service`
  - `$UI` = `$OM/openmetadata-ui/src/main/resources/ui/src`
  - `$DEP` = `deploy`
- 许可提醒：OM 服务端是 Apache-2.0，可以调用；OM UI 是 Collate Community License，按 UPSTREAM.yaml 不交付给客户使用。因此本文的 UI 部分只用于理解交互，织境界面自行实现，不复制 UI 代码。

## 1. 结论摘要

1. **搜索全部由 OM 服务端提供**：主搜索、聚合计数、筛选项、按类型计数都有现成 REST 接口，织境 BFF 只需转发并做参数校验，不用自建索引或搜索服务。
2. **Explore 左侧浏览树没有专门接口**：OM 前端用聚合查询逐层拼出来，层级是「服务类型 → 服务 → 库 → Schema → 实体类型」。织境可以照这个方式拼树。
3. **写入后立即可搜**：实体写入 OM 后，在同一请求线程里同步写入 OpenSearch（`refresh=true`）。005 采集结果和 006 开发态导入的元数据，都会自然出现在搜索结果里。
4. **中文分词未就绪**：当前部署用的是 EN 映射，OpenSearch 也没装 IK 分词插件（已实测核查）。中文检索效果需要实测验收后再决定是否切到 ZH 映射。
5. **搜索结果默认不按用户权限过滤**：`enableAccessControl` 默认是 `false`；`/aggregate` 和 `/entityTypeCounts` 即使开启也不过滤。这与宪法「Phase 1 不做数据层授权」的例外一致，但需要写进验收说明。
6. **2.0.3 没有 `/v1/search/suggest` 接口**：OM 前端的输入建议是用 `/search/query` 按类型分组实现的。
7. **补充调研（第 11–13 节，006 不实现）**：
   - 实体的定义：本体不是一类实体，而是建在术语实体上；
   - Context Center 文档的索引机制：与数据资产共用同一套实体事件，另外多了文字提取和可选的向量化；
   - 文档向量化与自定义嵌入：首选配置方式，即自建 OpenAI 兼容服务。用 OM 自带的向量化不需要 Airflow。

## 2. 搜索接口清单

源码：`$SVC/resources/search/SearchResource.java`，类级 `@Path("/v1/search")`（:96）。

| 接口 | 方法 | 关键参数 | 用途 | 出处 |
| --- | --- | --- | --- | --- |
| `/v1/search/query` | GET | `q`，`index`，`from`，`size`，`query_filter`，`post_filter`，`sort_field`，`sort_order`，`track_total_hits`，`include_source_fields`，`include_aggregations`，`search_after` | 主搜索，同时返回命中、高亮和聚合 | :110-323 |
| `/v1/search/entityTypeCounts` | GET | `q`，`index=dataAsset`，`query_filter`，`post_filter` | 按实体类型精确计数（`size=0`） | :837-897 |
| `/v1/search/aggregate` | GET / POST | `index`，`field`，`value`（桶值包含匹配），`q`，`size`；POST 支持 `topHits` | 单字段分桶，用于筛选项和浏览树 | :746-835 |
| `/v1/search/fieldQuery` | GET | `fieldName`，`fieldValue`，`index` | 按字段精确查 | :683-721 |
| `/v1/search/get/{index}/doc/{id}` | GET | — | 读单个索引文档 | :658-681 |
| `/v1/search/preview` | POST | 临时 searchSettings | 调整权重时预览结果，不保存 | :500-544 |
| `/v1/search/nlq/query` | GET | 同 `query` | 自然语言搜索；服务不可用时退回普通搜索 | :546-656 |
| `/v1/search/export(/async)` | GET | 同 `query` | 导出 CSV | :325、:431 |
| `/v1/search/reindexEntities` | POST | 实体引用（≤500） | 局部重建索引，仅管理员或机器人可用 | :899 |
| `/v1/system/settings/searchSettings` | GET / PUT / PATCH | — | 搜索字段权重、聚合、高亮、权限开关 | `$SVC/resources/system/SystemResource.java:252,589-624,659` |
| `/v1/tables/name/{fqn}` | GET | `fields`，`include` | 实体详情，供摘要面板使用 | `$SVC/resources/databases/TableResource.java:339-375` |
| `/v1/search/suggest` | — | — | **2.0.3 不存在** | `resources/search` 下没有该路由 |

`/query` 的返回要点：

- 返回 OpenSearch 的原始响应结构（`hits.total`、`hits.hits[]._source / highlight / sort`、`aggregations`），出处为 `$SVC/search/opensearch/OpenSearchSearchManager.java:1225`。
- 聚合键带 `sterms#` 前缀，OM 前端会自行去掉（`$UI/utils/ExplorePureUtils.ts:133-140`）。
- `q` 采用 query_string 语法，其中 AND / OR / NOT 必须大写（SearchResource.java:130-150）。
- `query_filter` 和 `post_filter` 是 ES DSL 的 JSON 字符串。**解析失败时只记日志、静默忽略该过滤**（OpenSearchSearchManager.java:900-926、1430-1438），所以 BFF 必须自己构造并校验。

## 3. 索引、别名与字段

- **别名注册**：`$OM/openmetadata-spec/src/main/resources/elasticsearch/indexMapping.json:2-26`。表的索引名是 `table_search_index`，别名为 `table`，父别名包括 `database`、`databaseSchema`、`databaseService`、`all`、`dataAsset`。
- **`index` 参数**可以填实体别名、索引名或逗号分隔的列表（`$SVC/search/SearchRepository.java:1006-1033`）。
- **`dataAsset` 别名覆盖 24 类实体**：table、**tableColumn**、storedProcedure、databaseSchema、database、dashboard、pipeline、topic、container、mlmodel、dataProduct、metric、glossaryTerm、tag 等。它包含列级文档，只要表时需要按类型过滤。
- **`all` 别名覆盖 53 类实体**：在 `dataAsset` 之外还加上各类服务、glossary、classification、domain、testCase 等。
- **表文档的关键字段**（映射文件 `$OM/openmetadata-spec/src/main/resources/elasticsearch/en/table_index_mapping.json`，生成代码 `$SVC/search/indexes/TableIndex.java:70-106`）：
  - 检索用：`name`、`displayName`（text，并带 keyword / ngram / compound 子字段）；`description`；`columns.name`；`columnNamesFuzzy`；`fullyQualifiedName`；`fqnParts`。
  - 筛选、聚合用（keyword 类型）：
    - `serviceType`、`entityType`
    - `service.displayName.keyword`、`database.displayName`、`databaseSchema.displayName`
    - `ownerDisplayName`、`domains.displayName.keyword`
    - `tags.tagFQN`、`tier.tagFQN`、`certification.tagLabel.tagFQN`
    - `classificationTags`、`glossaryTags`
  - 排序用：`totalVotes`、`updatedAt`、`usageSummary.*Stats.count`、`name.keyword`、`displayName.keyword`。

## 4. 查询如何构建

- **入口**：`$SVC/search/SearchSourceBuilderFactory.java:63-103`。数据资产类索引（含 `all` 和 `dataAsset`）都走 `buildDataAssetSearchBuilderV2`（`$SVC/search/opensearch/OpenSearchSourceBuilderFactory.java:420-444`）。
- **三种查询形态**（:446-456）：
  - 空串或 `*`：match_all。
  - 含查询语法：query_string，fuzziness 为 1。
  - 普通文本：按 searchFields 配置的 `matchType` 分组，exact 用 term，phrase 用 match_phrase，fuzzy 用带 fuzziness 的 multi_match，standard 用 multi_match（:969-1025、1268-1394）。
- **打分**：用 function_score 叠加 termBoosts（Tier1/2/3 等）和 fieldValueBoosts（月使用量）（:515-583）。
- **高亮**：默认对 `name`、`displayName`、`description` 高亮，命中词用 `<span class="text-highlighter">` 包裹（`$SVC/search/EntityBuilderConstant.java:27`）。
- **默认 searchSettings**：`$OM/openmetadata-service/src/main/resources/json/data/settings/searchSettings.json`，主要内容：
  - 全局：`enableAccessControl=false`、`maxAggregateSize=10000`、`maxResultHits=10000`（:3-5）。
  - 表的检索字段与权重（:360 起）：
    | 字段 | 匹配方式 | 权重 |
    | --- | --- | --- |
    | `displayName.keyword`、`name.keyword` | 精确 | 各 20 |
    | `name`、`displayName` | 短语 | 各 10 |
    | `*.compound` | — | 8 |
    | `fullyQualifiedName`、`fqnParts` | — | 各 5 |
    | `description` | — | 2 |
    | `columns.name.keyword` | — | 2 |
    | `columnNamesFuzzy` | — | 1.5 |
    | `*.ngram` | 模糊 | 1 |
  - 默认 15 个全局聚合：serviceType、service.displayName.keyword、entityType、tier.tagFQN、ownerDisplayName、domains.displayName.keyword、tags.tagFQN、classificationTags、glossaryTags、certification.tagLabel.tagFQN、database / databaseSchema 的名称等。
- **调权重**：通过 `/v1/system/settings/searchSettings` 修改，不需要改代码。这符合「先用 OM 能力、验收后再优化」：如果验收时发现排序不理想，优先调这里。
- **排序**：任意可排序字段都可以用。服务端总会追加 `name.keyword`、`_id` 作为平局时的排序依据（OpenSearchSearchManager.java:1451-1476）。

## 5. OM Explore 交互（来自 OM UI 源码，仅供参考）

| 交互点 | OM 行为 | 出处 |
| --- | --- | --- |
| 路由 | `/explore` 和 `/explore/:tab` 渲染同一个页面 | `$UI/constants/constants.ts:147-148` |
| 布局 | 顶部依次是快速筛选、排序、工具菜单、条件条；下方左栏是浏览树或类型菜单，右栏是结果、分页和摘要面板 | `$UI/components/ExploreV1/ExploreV1.component.tsx:721-946` |
| 搜索框 | 在导航栏，带搜索范围选择；输入防抖 400ms；建议按类型分组，每类最多 5 条，点击直接进详情；回车跳到 Explore 页并按相关性排序 | `$UI/components/GlobalSearchBar/GlobalSearchBar.tsx:88-175`，`$UI/components/AppBar/Suggestions.tsx:362-384` |
| 无关键词 | 左栏显示浏览树，查 `dataAsset`；条件条为空时显示提示文案 | `$UI/pages/ExplorePage/ExplorePageV1.component.tsx:287-290` |
| 有关键词 | 左栏换成类型菜单，只列计数大于 0 的类型；默认选中首条命中结果的类型，否则选计数最多的类型 | `$UI/utils/ExplorePureUtils.ts:114-131` |
| 浏览树 | 层级是「服务类型 → 服务 → 库 → Schema → 实体类型」；计数来自聚合的 `doc_count`；展开时懒加载；计数为 0 的根节点不显示；点击节点写入 URL 的 `browsePath`，当作位置条件，**不跳页** | `$UI/components/Explore/ExploreTree/ExploreTree.tsx:127-161,228-466` |
| 快速筛选 | 不分类型时提供：资产类型、域、数据产品、所有者、标签、Tier、服务、服务类型、认证；表类型额外提供：库、Schema、列、表类型、列描述 | `$UI/constants/AdvancedSearch.constants.ts:20-139` |
| 筛选逻辑 | 同一维度多选为 OR（`bool.should`），跨维度为 AND（外层 `must`）；某个维度的选项计数会排除本维度自身的条件 | `$UI/utils/ExplorePureUtils.ts:183-224`，`$UI/components/Explore/ExploreQuickFilters.tsx:146-242` |
| 空值筛选 | 所有者、域、Tier、标签、认证都可以选「无」，转成 `must_not exists` | `$UI/constants/explore.constants.ts:27-34` |
| 条件条 | 位置条件逐层显示，删除某一层会连同下层一起删掉；每个筛选值单独可删；「清除全部」 | `$UI/components/Explore/ExploreQueryFilterChips/ExploreQueryFilterChips.component.tsx:45-170` |
| 排序 | 热度（默认）、名称、相关性、更新时间；表类型另有周使用量；默认降序；改排序会回到第 1 页 | `$UI/constants/explore.constants.ts:40-106` |
| 分页 | 每页 15 / 25 / 50 条；`from=(页码-1)×每页条数` | `$UI/rest/searchAPI.ts:197-212` |
| URL 状态 | `:tab`、`search`、`quickFilter`、`browsePath`、`queryFilter`、`sort`、`sortOrder`、`currentPage`、`pageSize`、`showDeleted`；刷新后整体恢复；**选中的实体不写入 URL** | `$UI/utils/ExplorePureUtils.ts:866-906` |
| 结果卡片 | 面包屑（服务 / 库 / Schema）、图标和名称（链接到详情）、认证徽章、描述、域、所有者、Tier、使用量、命中字段统计；Explore 中不显示标签 | `$UI/components/ExploreV1/ExploreSearchCard/ExploreSearchCard.tsx:405-674` |
| 摘要面板 | 结果更新后自动选中第一条，无结果时关闭；按 FQN 补拉 `owners,domains,tags,extension`；页签有概览、Schema、血缘（深度 1）、数据质量、自定义属性；概览依次显示描述、所有者、域、Tier、术语、标签、数据产品；标题可点进详情页 | `$UI/components/Explore/EntitySummaryPanel/EntitySummaryPanel.component.tsx:254-470,888-984`，`$UI/components/DataAssetSummaryPanelV1/DataAssetSummaryPanelV1.tsx:521-620` |
| Tier 与标签 | Tier 按 `Tier.` 前缀识别，单独展示；标签区排除 Tier 和术语；认证是独立字段；**OM 没有专门的「安全级别」展示** | `$UI/utils/TablePureUtils.ts:75-83`，`$UI/components/common/TagsSection/TagsSection.tsx:59-75` |
| 其他 | 工具菜单里有导出、显示已删除、高级搜索（查询构建器）、排名详情；摘要面板里可以直接编辑所有者和标签 | `ExploreV1.component.tsx:769-827`，`EntitySummaryPanel.component.tsx:306-344` |

## 6. 索引写入链路

1. 实体的增删改依次经过 `EntityLifecycleEventDispatcher` → `SearchIndexHandler` → `SearchRepository.createEntityIndex / updateEntityIndex`（`$SVC/events/lifecycle/handlers/SearchIndexHandler.java:45-79`）。
2. `SearchIndexHandler.isAsync()=false`：事务提交后在请求线程里同步写入（:151-158），OpenSearch 写入带 `refresh=true`（`$SVC/search/opensearch/OpenSearchEntityManager.java:142,236,270`），所以写完立即可搜。
3. 写表文档时会同时写列文档（SearchRepository.java:1194-1201）。
4. 写索引失败不会让实体写入失败，只是进入重试队列，由后台 `SearchIndexRetryWorker` 重试，4xx 不重试（SearchRepository.java:1202-1212）。因此可能短暂出现「库里有、搜不到」。
5. 全量重建：`SearchIndexingApplication` 默认每周日 00:30 运行，也可以手动触发 `POST /v1/apps/trigger/{name}`。
6. 索引不存在时，`/query` 返回 404（OpenSearchSearchManager.java:1231-1237）。OM 前端遇到这种情况会显示「索引缺失」横幅。

## 7. 权限

- `/query` 本身不做授权检查。只有同时满足三个条件时才按策略过滤：`enableAccessControl=true`、用户不是管理员、存在策略求值器（`$SVC/search/SearchUtils.java:366-375`）。
- 默认值是 `false`，所以以用户委托令牌调用时，也能看到全部资产。
- `/aggregate` 和 `/entityTypeCounts` 不应用权限过滤（`$SVC/search/opensearch/OpenSearchAggregationManager.java:140-246,514-618`）。
- 对织境的影响：Phase 1 单租户，数据层授权按宪法例外推迟到二期（ADR-0012），所以默认值可以接受。BFF 仍然沿用 005 的用户委托令牌调用 OM（`services/bff/src/contexture_bff/adapters/om_client.py`），以后开启过滤时不用改调用方式。

## 8. 中文检索

- **语言配置**：映射语言支持 EN、JP、ZH、RU，默认 EN（`$OM/openmetadata-spec/src/main/resources/json/schema/configuration/elasticSearchConfiguration.json:9-19`），由环境变量 `ELASTICSEARCH_INDEX_MAPPING_LANG` 控制。
- **ZH 映射需要 IK 插件**：ZH 映射的 name、displayName、description、columns.name 使用 `ik_max_word` 建索引、`ik_smart` 检索（`.../elasticsearch/zh/table_index_mapping.json:95-96,122-123,146-147,360-361`），所以 OpenSearch 必须装 IK 分词插件。
- **本项目现状（已核查）**：
  - `$DEP/components/openmetadata/values/base.yaml:23-27` 没有设置语言，取 Chart 默认的 `EN`。
  - 2026-11-09 执行 `opensearch-plugin list`，结果中**没有 IK 插件**。
- **影响（推断，待实测）**：EN 映射用 standard 分词器，中文会被拆成单字。中文短语检索可能还能命中，但排序和模糊匹配的效果不确定。
- **建议**：006 先按现状（EN 映射）实现，在验收中用真实的中文显示名和描述测检索效果。如果不达标，再评估「安装 IK 插件、切换 ZH 映射、全量重建索引」。这属于部署变更，需要单独立项。

## 9. 局限与风险

| 项 | 说明 | 出处 |
| --- | --- | --- |
| 结果窗口 | `from` 和 `size` 都被截到 10000 以内；超过 10000 条需要用 `search_after` | OpenSearchSourceBuilderFactory.java:673-680 |
| 过滤被静默忽略 | `query_filter` 格式错误时不报错，直接忽略 | OpenSearchSearchManager.java:900-926 |
| 列文档混入 | `dataAsset` 包含 tableColumn，按资产类型组织结果时需要单独处理 | indexMapping.json |
| 查询超时 | 30 秒 | OpenSearchSearchManager.java:1508 |
| 用户级缓存 | 非机器人用户的 `/query` 结果会按用户缓存，刚写入的数据可能短暂看不到；需在验收中观察 | SearchResource.java:266-322 |
| 环境稳定性 | 本地 `opensearch-cluster-master-0` 已重启 286 次（2026-11-09 核查），会直接影响搜索验收，开发 006 前需要先排查 | `kubectl get pods` |

## 10. 对 006 的建议（优先复用 OM 能力）

1. **BFF 只做薄转发**：把结构化参数（关键词、类型、位置、筛选、排序、分页）转换成 OM 的 `q`、`index`、`query_filter`，并在 BFF 校验 DSL；浏览器不接触 DSL。
2. **接口映射**：
   - 主列表 → `/search/query`
   - 类型计数 → `/search/entityTypeCounts`
   - 筛选项和浏览树 → `/search/aggregate`
   - 摘要 → 实体接口（可以复用 005 的 `/bff/v1/catalog/{type}/{fqn}`）
3. **相关性先用 OM 默认的 searchSettings**，验收后再按需通过 settings 接口调整，不在 BFF 里自己算分。
4. **中文分词和搜索权限开关**都保持现状，作为验收观察项写进 acceptance.md。
5. **先复刻 OM Explore 的核心交互**：浏览树、类型、快速筛选、条件条、排序分页、卡片、摘要。高级搜索、导出、自然语言搜索、摘要内编辑这四项先不做，由负责人决定是否纳入（见页面结构方案的待决事项）。


---

以下第 11–13 节是 2026-11-09 负责人追问后补充的调研内容。**006 只做调研，不做任何自定义实现**：不开启向量化，不改嵌入模型，不打 OM 补丁。需要时另立项并补 ADR。

## 11. OM 的「实体」是什么

### 11.1 定义

实体（Entity）是 OpenMetadata 管理的每一类对象，相当于元数据目录里的一条记录。每类实体都具备以下四样：

1. 一份 JSON Schema 定义，在 `$OM/openmetadata-spec/src/main/resources/json/schema/entity/` 下；
2. 一张 OM PostgreSQL 表，也就是事实来源；
3. 一组 REST 接口，如 `/api/v1/tables`、`/api/v1/databases`；
4. 一个搜索索引，对应关系见 `indexMapping.json`。

所有实体都有统一的身份字段（`id`、`name`、`fullyQualifiedName`），也都带有通用的治理字段（owners、tags、domains、版本、变更记录）。OM 2.0.3 **不能新增实体类型**，见 [ADR-0008](../../../docs/adr/0008-本体六要素的实现.md) 背景。

### 11.2 常见类别

| 类别 | 实体举例 | 和织境的关系 |
| --- | --- | --- |
| 数据资产 | databaseService、database、databaseSchema、table、dashboard、pipeline、topic 等 | 005 采集写入的就是这一类，006 主要搜索这一类 |
| 治理对象 | glossary / glossaryTerm、classification / tag（Tier、「数据级别」都属于这里）、domain、dataProduct、metric | 织境本体建在术语上；Tier 和数据级别都是标签 |
| 人员与权限 | user、team、role、policy | 所有者筛选、令牌委托 |
| Context Center（2.0.3 新增） | page（页面）、contextFile（上传文件）、contextMemory（记忆） | 见第 12 节 |

### 11.3 实体写入与搜索索引的关系（补充第 6 节）

- `SearchIndexHandler` 是 **OM 服务端进程里的 Java 事件处理类，不是 Airflow 管线**（`$SVC/events/lifecycle/handlers/SearchIndexHandler.java`）。
- **触发单位是单个实体，与数据源无关**：不论实体来自 005 采集、开发态导入还是页面编辑，只要经 OM REST 接口写入，就会触发它。
- **索引按实体类型划分，所有数据源共用**：例如所有表都进 `table_search_index`。文档里的 `service.name`、`serviceType`、`fullyQualifiedName` 用来区分来源，浏览树和筛选就是聚合这些字段得到的。
- **同步执行**：在请求线程上执行（`isAsync()=false`，:151-158），失败时放入 OM 内部的重试队列。全量重建由 OM 内置应用 `SearchIndexingApplication` 负责（`appType: internal`，由 OM 进程内的 Quartz 调度器运行，默认每周日 00:30）。
- **不占用 Airflow 资源**：资源消耗在 OM 服务器和 OpenSearch 上。采集任务的耗时里包含同步写索引的时间。

### 11.4 本体不是一类实体

| 层 | 承载方式 | 出处 |
| --- | --- | --- |
| 织境业务本体（对象、关系、属性） | 全部建为 **glossaryTerm 实体**：用术语全局自定义属性 `ctx_kind`、`ctx_uri` 等区分要素，对象到属性用自定义关系 `hasProperty`，属性贴「数据级别」标签。它们会正常进入 `glossary_term_search_index`，006 能搜到 | ADR-0008 第 2 节 |
| OM 自带的元数据本体 | OM 用 OWL + SHACL 描述自身的实体模型，并把实体投影到 Jena Fuseki（RDF，Beta）。这是第二套存储，不是搜索索引。**投影由什么触发，尚未追溯源码** | `$SVC/rdf/`（OntologyLoader、GlossaryRdfImporter、sql2sparql、reasoning 等） |

## 12. Context Center 怎么给文档建索引

**结论：底层和数据资产是同一套实体事件机制，但文档多了「文字提取」和「向量化」两层。向量化默认关闭，本项目部署也没有开启。**

| 层 | 机制 | 与 `SearchIndexHandler` 的关系 | 出处 |
| --- | --- | --- | --- |
| ① 文件入库 | 上传 PDF、文档、表格，生成 `contextFile` 实体，文件本体存在 Drive（AssetService，可以是 S3 或 Azure） | 和普通实体一样 | `$OM/openmetadata-spec/src/main/resources/json/schema/entity/data/contextFile.json`，`$SVC/resources/drive/ContextFileResource.java` |
| ② 文字提取 | `ContextFileExtractionService` 在 **OM 进程内的独立线程池里异步执行**：PDF 用 PDFBox，其他格式用 Tika，图片需要另装 tesseract 才能 OCR；结果写回 `extractedText` 和 `processingStatus` | 文档特有的步骤 | `$SVC/drive/ContextFileExtractionService.java:31-127`，`$SVC/drive/ContextFileTextExtractor.java:57-145` |
| ③ 关键词索引 | 提取结果写回实体时，触发**同一个** `SearchIndexHandler`，写入 `context_file_search_index`（别名只挂在 `all` 下）；`extractedText` 是检索字段，权重 2 | **同一套** | `$SVC/search/indexes/ContextFileIndex.java:28-46`，`indexMapping.json:641-651` |
| ④ 向量索引 | 另一个处理器 `VectorEmbeddingHandler` 也挂在实体事件上，但**是异步的**（它没有覆盖接口默认的 `isAsync()=true`）。流程是：切块 → 调用嵌入模型 → 写入 OpenSearch kNN 块索引，同时把第一块的向量写回实体文档，供混合检索使用 | 同一套事件机制，另一个处理器 | `$SVC/search/vector/VectorEmbeddingHandler.java:31-130`，`$SVC/events/lifecycle/EntityLifecycleEventHandler.java:139-141` |

补充事实：

- **页面（page）和记忆（contextMemory）** 都挂在 `dataAssetEmbeddings` 别名下，页面还挂在 `dataAsset` 下（`indexMapping.json:627-651`）。所以 006 的 `dataAsset` 搜索可能会出现页面，具体按类型清单处理。
- **能向量化的实体类型是写死的清单**（`$SVC/search/vector/utils/AvailableEntityTypes.java`），包括表、库、Schema、术语、页面、记忆、指标、数据产品等。**上传文件 contextFile 不在清单里**，只有关键词索引。
- **向量化的开关**：需要 `naturalLanguageSearch.semanticSearchEnabled=true`（默认 `false`），并配好嵌入模型，否则不初始化（`$SVC/search/SearchRepository.java:735-744`，`$OM/conf/openmetadata.yaml:606-607`）。本项目 `deploy/components/openmetadata` 没有设置这些，所以**当前只有第 ③ 层生效**。
- **没有找到从文件自动生成记忆的代码**：服务端没有调用 `setSourceFile` 的地方。记忆看起来是由接口或 AI 对话写入的，这一点尚未完全核实。
- **以上各层都在 OM 进程内执行，不经过 Airflow。**

## 13. 文档向量化与自定义嵌入方式（仅调研，006 不实现）

### 13.1 可选做法（按宪法「配置 → 扩展点 → 补丁」的顺序）

| 做法 | 能做到什么 | 代价与限制 | 出处 |
| --- | --- | --- | --- |
| A. 改配置：自建模型服务 | 设 `EMBEDDING_PROVIDER=openai`，并把 `endpoint` 指向**自建的 OpenAI 兼容服务**（如私有部署的 bge-m3、TEI、vLLM），OM 会请求 `{endpoint}/embeddings`。算法完全由自建服务决定 | 不改 OM 代码，**是自定义嵌入算法的首选**。注意嵌入和对话大模型共用 `llmConfiguration.openai` 的 endpoint 和 apiKey；向量维度要在配置里写对 | `$SVC/search/vector/client/OpenAIEmbeddingClient.java:39-123`，`$OM/conf/openmetadata.yaml:610-660` |
| B. 改配置：本地模型 | 设 `provider=djl`，在 OM 的 JVM 里运行 DJL 模型库中的 HuggingFace 句向量模型 | 占用 OM 服务器的 CPU 和内存；只能用 DJL 能加载的模型 | `$SVC/search/vector/client/DjlEmbeddingClient.java:50-54` |
| C. 补丁 | 新增 `EmbeddingClient` 实现，或修改切块、预处理逻辑 | 模型提供方在代码里写死为四选一（bedrock、openai、google、djl），**没有插件扩展点**。只能改源码，登记 `third_party/openmetadata/PATCHES.md`，并按宪法 VI 维护 | `$SVC/search/SearchRepository.java:4404-4436` |

### 13.2 已知限制

1. **上传文件不会被向量化**：contextFile 不在可向量化清单里。要向量化文档，只能把内容写成页面实体，或者打补丁。
2. **切块对中文不友好**（源码推断，未实测）：`TextChunkManager` 按空白字符切词，每 380 个「词」切一块，**单个「词」长度达到 600 字符会被直接跳过**。中文没有空格，长段落可能整段被当成一个「词」而丢失（`$SVC/search/vector/utils/TextChunkManager.java:13-45`）。
3. **没有外部写入向量的接口**：向量检索接口只有查询（`POST /v1/search/vector/query`，`$SVC/resources/search/VectorSearchResource.java:48`），没有找到把外部算好的向量写回 OM 索引的接口。
4. **外部调用和数据出境**：开启后，每次写入可向量化实体都会调用一次嵌入模型。如果用外部云模型，元数据会离开本地环境，需要另做合规评估。

### 13.3 是否需要 Airflow

- **使用 OM 自带的向量化不需要 Airflow。** 增量向量化在实体写入时于 OM 进程内异步执行；全量重建由 OM 内置的 Quartz 调度运行 `SearchIndexingApplication`。
- **只有决定不用 OM 的向量化时才需要 Airflow**：例如为了中文切块、自定义算法或大批量回补，用 Airflow 调度外部管线，写入织境自己维护的向量索引。代价是 OM 的语义搜索用不到这些向量，查询入口要织境自建，服务边界随之扩大，必须另写 ADR。

### 13.4 后续建议（不在 006 范围内）

1. 如果要做文档向量化，优先选做法 A：把自定义算法封装成 OpenAI 兼容服务，不改 OM。
2. 先用真实中文文档实测切块和检索效果，确认是否丢内容，再在「打补丁」和「外部管线」之间决定。
3. 立项时同时补 ADR，写清模型选型、部署位置、数据出境与合规、资源占用（OM 服务器与 OpenSearch kNN）。
