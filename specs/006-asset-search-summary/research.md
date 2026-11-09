# Research: 资产搜索与摘要（006）

**Date**: 2026-11-09 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

本研究基于锁定源码 `third_party/openmetadata/src`（上游 `2.0.3-release`，提交 `b76076bf`）与当前仓库。
[OM 搜索能力对齐调研](prototype/openmetadata-alignment.md)（下称「对齐调研」）已经确立的结论直接引用，不重复；
本文只补充 plan 需要落定的细节，并修正对齐调研中与源码不符的一处（R11：索引缺失返回 500，不是 404）。

路径缩写同对齐调研：`$SVC` = `openmetadata-service/src/main/java/org/openmetadata/service`，
`$UI` = `openmetadata-ui/src/main/resources/ui/src`，`$SPEC` = `openmetadata-spec/src/main/resources`，
`$RES` = `openmetadata-service/src/main/resources`。OM UI 为 Collate Community License，只读来理解交互，不复制代码。

未能在源码中确认的事项原标为 UNCONFIRMED，已在实施阶段（2026-11-09）以集成测试实测确认，结论见各节「实测」与文末「实施中的修正」，并写入 `acceptance.md`。

---

## R1：OM 接口分工与统一约定

- **Decision**：
  | 织境用途 | OM 接口 | 关键参数 |
  | --- | --- | --- |
  | 主列表 | `GET /v1/search/query` | `q`、`index`、`from`、`size`、`query_filter`、`sort_field`、`sort_order`、`track_total_hits=true`、`deleted=false` |
  | 类型计数（类型列表、搜索范围选项） | `GET /v1/search/entityTypeCounts` | `q`、`index=dataAsset`、`query_filter` |
  | 首条命中结果的类型 | `GET /v1/search/query` | `index=dataAsset`、`size=1`、`include_source_fields=entityType` |
  | 快速筛选选项、浏览树各层计数 | `GET /v1/search/aggregate` | `index`、`field`、`value`、`q`（DSL 过滤）、`queryText`、`size`、`sourceFields`、`deleted=false` |
  | 输入建议 | `GET /v1/search/query` | 同主列表，`size=15` |
  | 摘要、术语 / 标签详情 | `GET /v1/{集合}/name/{fqn}` | `fields` 见 R9 |
  
  所有请求都由 BFF 发出，并沿用 005 的 `OmClient`（用户委托令牌，`services/bff/src/contexture_bff/adapters/om_client.py:48-113`）。
- **统一约定**：
  - **软删除**：`/search/query` 不传 `deleted` 时不过滤，会返回已软删除的实体（`$SVC/search/opensearch/OpenSearchSearchManager.java:933-986`；`$SPEC/json/schema/search/searchRequest.json:57-62`）。OM UI 总是传 `deleted=false`（`$UI/rest/searchAPI.ts:168`）。`/entityTypeCounts` 只在 `deleted=true` 时才加过滤（`$SVC/search/opensearch/OpenSearchAggregationManager.java:550-563`）。因此 BFF **每次**都传 `deleted=false`，并在交给 `/entityTypeCounts` 的 `query_filter` 里显式加上 `term deleted=false`，保证计数与列表范围一致。这对应 spec D5「006 不做显示已删除」。
  - **聚合键前缀**：OM 返回 OpenSearch 原始结构，聚合键带 `sterms#` 前缀（对齐调研第 2 节）。BFF 去掉前缀后再投影。
- **Rationale**：FR-018 要求主列表、类型计数、筛选项、浏览树计数分别使用 OM 的主搜索、按类型计数和聚合能力。以上全部是 OM 公开 REST 接口（Apache-2.0）。
- **Alternatives considered**：
  - 按 OM UI 的做法，用 `/search/query` 的聚合取类型计数（`$UI/utils/ExploreUtils.tsx:213-260`），不调 `/entityTypeCounts`。没有采用，因为 FR-007 / FR-018 明确写的是「按类型计数」能力。`/entityTypeCounts` 与 `/search/query` 使用同一个打分查询构造器，`aggregations["sterms#entityType"]` 的结果等价（OpenSearchAggregationManager.java:514-618）。
  - BFF 直连 OpenSearch：违反 FR-019 与宪法 II、VI，否决。

## R2：结构化条件 → OM 查询（FR-019）

- **Decision**：浏览器只提交 `SearchCriteria`（结构见 [data-model.md](data-model.md) 第 2 节）。BFF 按下列规则生成 OM 参数；不合法时返回 `422 search.invalid_criteria`，并在 `details` 中指明是哪个字段、什么原因。
  - **索引 `index`**：
    - 有资产类型（左栏选中的类型，或搜索范围）时，取该类型的 OM 别名，如 `table`、`database`、`databaseSchema`、`tableColumn`、`glossaryTerm`、`tag`。别名清单见 `$SPEC/elasticsearch/indexMapping.json:2-26`。`index=table` 只解析到 `table_search_index`，不含列文档（`$SVC/search/SearchRepository.java:1023-1034`）。
    - 没有类型时用 `dataAsset`。这时结果里会包含列文档，与 OM Explore 无关键词时的行为一致：数据库大类的子实体包含 tableColumn（`$UI/utils/SearchClassBase.ts:236-420`）。spec 边界情况「列结果混入」只要求列不混进**表**的计数与结果，`index=table` 已经满足。验收时观察「全部资产」列表中列的占比，记入 `acceptance.md`。
    - 类型取值以白名单校验，白名单就是 `dataAsset` 别名覆盖的实体类型（indexMapping.json）。
  - **关键词 `q`**：
    - 去掉首尾空白，空串改为 `*`（match_all）。
    - 先转义 query_string 的保留字符（`+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /`），再把单独出现的大写 `AND` / `OR` / `NOT` 改为小写，使关键词始终按普通文本处理。OM 会把含查询语法的输入走 query_string（`$SVC/search/opensearch/OpenSearchSourceBuilderFactory.java:446-456`），而 AND / OR / NOT 只有大写才是运算符（SearchResource.java:130-150）。
    - 长度上限 200 字符。这是 BFF 的防护上限，不是产品选项；每个筛选维度最多 50 个取值也是同样性质（data-model 第 2 节）。
  - **过滤 `query_filter`**：BFF 构造 `{"query":{"bool":{"must":[...]}}}`，各部分如下：
    - 位置条件：每层一个 `term`（R3）。
    - 筛选维度：同一维度内多个取值用 `bool.should[term]`，「无」用 `bool.must_not.exists(field)`，两者放在同一个 `should` 中；跨维度放进外层 `must`。这与 `$UI/utils/ExplorePureUtils.ts:183-224` 的组合方式一致。
    - 软删除：`term deleted=false`。
    
    构造结果由 BFF 序列化，不接受浏览器提交的 DSL。原因是 OM 解析 `query_filter` 失败时只记日志、静默忽略（对齐调研第 2 节），所以 BFF 用单元测试保证生成的 DSL 结构合法。
  - **分页**：`from=(page-1)×pageSize`，`pageSize ∈ {15, 25, 50}`。`from + pageSize > 10000` 时返回 `422 search.window_exceeded`，界面提示缩小条件（R6）。
- **Rationale**：满足 spec 边界情况「查询语法字符」与 FR-019「不合法的条件 MUST 返回明确错误，MUST NOT 被静默忽略」。
- **Alternatives considered**：把原始关键词直接交给 OM（OM UI 的做法），用户输入 `a AND`、`(` 之类时可能报错或语义改变，否决。用 `search_after` 突破 10000 条：OM UI 的普通分页也不用它，006 不做。
- **验证**：集成测试用含 `( ) : " AND OR NOT * ?` 的关键词实测，确认不报错、筛选不被忽略（与同条件的结果数对比）。

## R3：浏览树（FR-006）

- **Decision**：
  - **根节点**：采用 OM 的静态大类清单（`$UI/utils/SearchClassBase.ts:236-420`，`getExploreTree`），每个大类对应一组子实体类型。
    - 数据库类：database、databaseSchema、storedProcedure、table、tableColumn。
    - 治理类：tag、glossaryTerm、metric（:347-404）。
    - 其他大类（仪表板、管道、消息主题等）同样列入。计数为 0 的根节点不显示，所以 Phase 1 实际只会出现有数据的大类。
    
    清单作为 BFF 常量维护，注明出处。它是数据，不是 UI 代码。
  - **层级字段**：取自 `$UI/utils/ExplorePureUtils.ts:226-258`。
    - 数据库类：`serviceType` → `service.displayName.keyword` → `database.displayName` → `databaseSchema.displayName` → `entityType`。
    - 其他大类：`serviceType` → `service.displayName.keyword` → `entityType`。
    - 治理类：直接到 `entityType`。OM UI 在这里放的是静态叶子（术语表 / 标签 / 指标）。
  - **计数来源**：
    - 根节点：对 `dataAsset` 做一次 `/search/aggregate`，`field=entityType.keyword`，再按大类清单把各类型的计数相加。
    - 子层：每展开一层，用一次 `/search/aggregate`，`field` 取该层字段，`q` 为「父路径各层 term + 当前筛选条件」的 DSL。这与 `buildTreeCountQueryFilter`（ExplorePureUtils.ts:619-659）一致：在根层还要限定该大类的子实体类型，计数会随当前快速筛选变化。
    - OM UI 在非服务层改用 `/search/query` 的聚合（`ExploreTree.tsx:127-161`）。织境统一用 `/aggregate`，结果等价，接口更少，也符合 FR-018「浏览树计数使用聚合能力」。
  - **按需加载**：BFF 提供 `POST /bff/v1/assets/browse`。请求带父路径，只返回下一层的节点；前端只在展开时请求。
  - **点击节点**：前端把「根 + 各层 `{level, value}`」写入搜索条件中的 `browsePath`，不跳页。BFF 把每一层转成 `term`。
  - **实施调整**：浏览树各层改用原始大小写的 keyword 字段（`entityType`、`service.displayName`、`database.displayName`、`databaseSchema.displayName`；`serviceType` 只有小写字段，显示名取 top_hits），桶键即显示名，省去 OM UI 的「小写桶键 + top_hits 取显示名」。字段类型见 `$SPEC/elasticsearch/en/table_index_mapping.json`（均为 keyword），计数口径与 OM 相同。
  - **桶数量与顺序**：`/aggregate` 的桶按键名字母升序返回，不按计数排序（OpenSearchAggregationManager.java:262-292）。浏览树每层取 `size=1000`，远小于 OM 的 `maxAggregateSize=10000`；顺序保持 OM 的返回顺序。
- **Rationale**：FR-006 要求「服务类型 → 服务 → 库 → Schema → 实体类型」、计数来自聚合、按需加载、点击只设置位置条件；以上都按 OM 现有做法实现。005 原来的逐层 REST 分页计数（`om_sources.py:854-893`）不再用于浏览树。
- **实测（2026-11-09，`test_om_unconfirmed_cluster.py`、`test_assets_browse_cluster.py`）**：
  - 没有 `displayName` 的实体，索引中 `displayName` 回退为 `name`（fixture 中的 `supplier` 表）；服务没有显示名时，`service.displayName` 同样为服务名。
  - `database.displayName` 是 keyword 字段，可直接聚合。
  - `/search/aggregate` 必须传 `value=.*`：不传时 `value` 默认为空串，OM 按空的 include 正则过滤，返回空桶。
  - fixture 中每张表都能经浏览树「服务类型 → 服务 → 库 → Schema」定位；数据库大类计数与 OM 直接聚合一致。

## R4：快速筛选（FR-008）

- **Decision**：维度与 OM 字段的对应如下（`$UI/constants/AdvancedSearch.constants.ts:69-139`）：

  | 维度（文案） | OM 字段 | 选项显示名来源 | 支持「无」 |
  | --- | --- | --- | --- |
  | 资产类型 | `entityType.keyword` | — | 否 |
  | 业务域 | `domains.displayName.keyword` | `domains.displayName` | 是 |
  | 数据产品 | `dataProducts.displayName.keyword` | — | 否（见下） |
  | 负责人 | `ownerDisplayName` | — | 是 |
  | 分类标签 | `tags.tagFQN` | — | 是 |
  | 分级（Tier） | `tier.tagFQN` | — | 是 |
  | 服务 | `service.displayName.keyword` | `service.displayName` | 否 |
  | 服务类型 | `serviceType` | — | 否 |
  | 认证 | `certification.tagLabel.tagFQN` | — | 是 |
  | 库（仅表类型） | `database.displayName.keyword` | `database.displayName` | 否 |
  | Schema（仅表类型） | `databaseSchema.displayName.keyword` | `databaseSchema.displayName` | 否 |
  | 列（仅表类型） | `columns.name.keyword` | — | 否 |
  | 表类型（仅表类型） | `tableType` | — | 否 |
  | 列描述（仅表类型） | `columnDescriptionStatus` | — | 否 |

  - 「无」的范围按 spec FR-008：负责人、业务域、分级、分类标签、认证。OM 对数据产品也支持「无」（`$UI/constants/explore.constants.ts:27-34`），但 spec 没有列，006 不做。
  - 仅表类型可用的维度出现在非表类型的请求中时，返回 `422 search.invalid_criteria`。
- **选项计数排除本维度**：对应 `$UI/components/Explore/ExploreQuickFilters.tsx:146-242`。请求某个维度的选项时，BFF 用「关键词 + 位置 + **其他**维度的已选条件」作为 `/aggregate` 的 `q`（DSL），关键词放在 `queryText`。BFF 接口 `POST /bff/v1/assets/facets` 一次只返回一个维度。
- **选项内搜索**：`value` 传 `.*<转义后的输入>.*`（`$UI/rest/miscAPI.ts:226-229`）。OM 服务端会转小写，按精确、前缀、包含三档合并去重（`$SVC/search/SearchUtils.java:118-230`）。
- **选项显示名与取值**：带 `lowercase_normalizer` 的字段，桶键是小写的。BFF 传 `sourceFields=<显示名来源字段>`，从 top_hits 中取原始大小写作为显示名；筛选时仍用桶键做 `term`（OpenSearchAggregationManager.java:204、248-260）。
- **「无」不显示计数**：OM 的「无」选项只是一个复选框，没有计数（`$UI/components/SearchDropdown/SearchDropdown.tsx:391-412`）。006 保持一致。spec FR-008「显示选项计数」只适用于有取值的选项。
- **每次取多少选项**：采用 `/aggregate` 的默认值 `size=10`（SearchResource.java:746-812），更多选项通过选项内搜索查找。已核对：OM Explore 的快速筛选不传 `optionPageSize`，`getAggregateFieldOptions`（`$UI/rest/miscAPI.ts:216-245`）也不传 `size`，即服务端默认 10，与 BFF 一致。
- **已知差异**：列文档没有 `ownerDisplayName`（`$SVC/search/indexes/ColumnSearchIndex.java:107`），所以按负责人筛选时不会出现列。这与 OM 行为一致，写进 `acceptance.md`。

## R5：排序（FR-010）

- **Decision**：映射取自 `$UI/constants/explore.constants.ts:19,40-106`。

  | 织境 | `sort_field` |
  | --- | --- |
  | 热度（默认） | `totalVotes` |
  | 名称 | `displayName.keyword` |
  | 相关性 | `_score` |
  | 最近更新 | `updatedAt` |

  - 默认 `desc`。用户回车搜索时，前端把排序设为「相关性」（FR-004；OM 的做法见 `ExplorePageV1.component.tsx:211-230`）。
  - 改变排序或升降序时，页码回到 1。
  - OM 服务端会追加 `name.keyword`、`_id` 作为平局时的排序依据（对齐调研第 4 节）。
  - 表类型独有的「周使用量」排序不在 spec 中，不做。

## R6：结果窗口上限与超时

- **结果窗口**：OM 把 `from` 和 `size` 分别截到 10000 以内，但不检查两者之和（OpenSearchSourceBuilderFactory.java:673-680）。索引没有设置 `max_result_window`。实测：`from=9995,size=15` 时 OM 返回 HTTP 500「Search failed … Result window is too large」；BFF 在调用 OM 之前即返回 422 `search.window_exceeded`。
  - **Decision**：BFF 先行校验 `from + size ≤ 10000`。超出时返回 `422 search.window_exceeded`。
  - 前端把可翻到的最大页码限制在窗口以内；总数超过 10000 时，在分页处提示「仅显示前 10000 条，请缩小条件」。
  - 页头显示的总数仍取 `hits.total.value`（`track_total_hits=true`），即真实总数。
- **超时**：OM 给 OpenSearch 设了 `timeout("30s")`（OpenSearchSearchManager.java:1508）。触发时 OpenSearch 返回部分结果、`timed_out:true`、HTTP 200。实测：本地数据量下无法触发超时（`size=10000` 查询 `timed_out=false`，约 140–190ms），返回形式未能在真实环境复现；映射逻辑由契约测试（模拟 `timed_out=true`）保证。
  - **Decision**：BFF 发现 `timed_out=true` 时，不返回部分结果，而是返回 `504 search.timeout`，满足「不显示伪造或不完整的结果」。
  - BFF 的 OM 客户端超时沿用 005 的 30 秒（`om_client.py:61`）。超时后映射为 `502 upstream.unavailable`。

## R7：输入建议（FR-005）

- **Decision**：
  - 一次请求：`/search/query`，`index` 取搜索范围对应的别名，没有选范围时用 `dataAsset`；`size=15`，`deleted=false`；`include_source_fields` 只取 `id, name, displayName, fullyQualifiedName, entityType, serviceType, service.displayName`，避免返回字段清单。
  - BFF 按 `_source.entityType` 分组，每组最多 5 条（`$UI/utils/SearchUtils.tsx:225-241`；`$UI/components/AppBar/Suggestions.tsx:362-384`）。
  - 每条显示名称与位置（FQN），点击后的进入方式按 R8。
  - 前端防抖 400ms（`$UI/components/GlobalSearchBar/GlobalSearchBar.tsx:133`）。
  - 新输入发出时，取消上一个未完成的请求（react-query 的 `signal`），丢弃过期结果。
- **Rationale**：OM 2.0.3 没有建议接口（对齐调研第 2 节）。spec FR-005 要求使用与主搜索相同的能力。

## R8：高亮与命中字段统计（FR-011）

- **Decision**：
  - **高亮**：高亮来自 OM 返回的 `highlight`，命中词用 `<span class="text-highlighter">` 包裹（`$SVC/search/EntityBuilderConstant.java:27`）。BFF **不**把 HTML 交给浏览器，而是解析成片段数组 `[{text, match: bool}]`，前端按片段渲染，避免把 OM 返回的 HTML 直接插入页面。OM 返回的是转义前的文本，转换规则用单元测试覆盖。
  - **命中字段统计**：与 OM 一致（`$UI/components/SearchedData/SearchedData.tsx:55-60`）。对 `highlight` 的每个键，去掉含 `.ngram` 的键以及 `table_name` 等，统计各键的片段数。
  - **高亮字段**：只能通过 OM searchSettings 配置，`/search/query` 没有对应参数（OpenSearchSourceBuilderFactory.java:659-670）。表的高亮字段是 `name, description, displayName`（`$RES/json/data/settings/searchSettings.json:447-451`），因此只命中字段名时，表卡片上没有高亮。这是 OM 默认行为，006 不调整（FR-018），并写进 `acceptance.md`。

## R9：摘要、术语详情与标签详情的读取（FR-012、FR-013）

- **摘要 Decision**：新增 `GET /bff/v1/assets/summary/{entityType}/{fqn}`，按类型读取 OM 实体。

  | 类型 | OM 接口 | `fields` |
  | --- | --- | --- |
  | table | `/v1/tables/name/{fqn}` | `owners,domains,tags,dataProducts,columns,tableConstraints,certification` |
  | database / databaseSchema | `/v1/databases`、`/v1/databaseSchemas` | `owners,domains,tags,dataProducts,certification` |
  | glossaryTerm | `/v1/glossaryTerms/name/{fqn}` | `owners,domains,tags,reviewers` |
  | tag | `/v1/tags/name/{fqn}` | `owners,domains,reviewers` |
  | tableColumn | 先由列 FQN 算出所属表 FQN（R10），读表实体并取出该列 | 同 table |
  | 其他 dataAsset 类型 | 对应集合的 `/name/{fqn}` | `owners,domains,tags` |

  - 允许的 `fields` 就是实体 JSON 的全部属性（`$SVC/Entity.java:903-906`）。table 的常用字段见 `TableResource.java:109-111`。`certification` 是 table 的 schema 属性，可以请求（`$SVC/jdbi3/EntityRepository.java:732-758`）。实施时用集成测试确认 database / databaseSchema 也有 `certification`，没有就去掉。
  - 分级（Tier）、数据安全级别、业务术语、分类标签都在 `tags` 中，按前缀拆分（FR-014）：
    - `Tier.` 开头的是分级（005 已有，`governance_view`，`om_sources.py:1018-1035`）；
    - `数据级别.` 开头的是数据安全级别（ADR-0008 第 2.4 节；分类名与 `tools/seed.py:27` 的 `DATA_LEVEL` 一致）；
    - `source=Glossary` 的是业务术语；
    - 其余是分类标签。
  - 认证取 `certification.tagLabel`。
  - 摘要与列表共享身份 `{entityType, id, fqn}`。BFF 返回读取到的 `id`，前端核对它与列表项的 `id` 一致，不一致时显示真实错误，防止选中项串号（spec 边界情况「同名资产」）。
  - **为什么不直接复用 005 的 `GET /bff/v1/catalog/{type}/{fqn}`**：它会逐层计算子节点和计数（`om_sources.py:854-909`），摘要用不上，代价也高；而且它的类型参数只接受四种数据库类实体（`api/catalog.py:12`）。因此新增一个只读摘要接口，复用 `OmClient` 和 005 的 `governance_view` 拆分逻辑。库、Schema、表进入详情页后，仍使用 005 的 catalog 接口。
- **术语与标签详情 Decision**：新增 `GET /bff/v1/governance/glossary-terms/{fqn}` 和 `GET /bff/v1/governance/tags/{fqn}`。字段只取 OM 实体的原生属性，属性定义见 `$SPEC/json/schema/entity/data/glossaryTerm.json`、`$SPEC/json/schema/entity/classification/tag.json`。
  - **字段清单（负责人 2026-11-09 确认：采用以下 OM 原生字段候选清单）**：
    - 业务术语：名称、显示名称、完整名称（FQN）、所属术语表（`glossary`）、上级术语（`parent`）、描述、同义词（`synonyms`）、相关术语（`relatedTerms`）、参考链接（`references`）、负责人（`owners`）、评审人（`reviewers`）、业务域（`domains`）、分类标签（`tags`）、状态（`entityStatus`）。
    - 分类标签：名称、显示名称、完整名称（FQN）、所属分类（`classification`）、上级标签（`parent`）、描述、负责人、评审人、业务域、是否已弃用（`deprecated`）。
  - 原型 `prototype/index.html` 的术语、标签详情示意已按此清单同步（FR-013「先补原型并经负责人确认」）。空值显示「—」或「未设置」，不补造。
  - 实体不存在时，OM 返回 404，BFF 映射为 `404 catalog.not_found`，页面显示「未找到」。

## R10：列结果跳转所属表并定位（Q3 = A）

- **Decision**：
  - 列文档带有 `table.fullyQualifiedName`（`$SVC/search/indexes/ColumnSearchIndex.java:54-146`）。BFF 在搜索结果和建议中，为列项直接给出 `parentTable: {fqn, id}` 和 `columnName`，不需要前端拆 FQN。
  - 点击列结果后，前端进入 `/assets/table/{表 FQN}`，把要定位的列名放在路由的 `location.state` 中，不写进地址（D9 不写地址状态）。
  - 005 的表详情页读到这个状态后，滚动到该列所在行并高亮显示（原型预设「12. 列结果 → 表详情定位」）。刷新页面后状态丢失、不再定位，这是预期行为，与 spec 的「刷新页面」边界情况一致。
- **Rationale**：OM UI 也是用列 FQN 跳到表页面，前 4 段是表 FQN，其余是列名（`$UI/utils/EntityUtilClassBase.ts:599-619`）。BFF 直接使用索引中现成的 `table.fullyQualifiedName`，可以避开含点号、带引号的 FQN 的拆分问题。
- **列的摘要**：选中列卡片时，摘要读所属表的实体，只显示该列的信息（名称、类型、约束、描述、分类标签），再加上所属表的位置。

## R11：页面状态与错误映射（FR-015）

| 情况 | OM 表现 | BFF 返回 |
| --- | --- | --- |
| OM 不可达或 5xx | 网络错误 / 5xx | `502 upstream.unavailable`（沿用 `om_client.py:89-107`） |
| 索引缺失 | **HTTP 500**，消息为 `Failed to find index …`（OpenSearchSearchManager.java:1231-1237；`CatalogGenericExceptionMapper.java:73-83`）。**对齐调研第 6 节写的 404 有误，以此为准** | `503 search.index_missing`（BFF 按消息前缀识别） |
| OpenSearch 超时 | `timed_out:true`（R6） | `504 search.timeout` |
| 结果窗口超限 | — | `422 search.window_exceeded` |
| 条件不合法 | — | `422 search.invalid_criteria` |
| 术语、标签或资产不存在 | 404 | `404 catalog.not_found` |
| 令牌无权限 | 401 / 403 | `403 auth.om_forbidden` |

- 零资产：根节点计数全为 0，或 `dataAsset` 上 `*` 查询的总数为 0。前端显示零资产空状态，引导用户去「添加数据源」，并说明可以用开发态导入。
- 所有错误都沿用 `contracts/schemas/error.json` 的结构（`code`、`message`、`trace_id`、`details`）。前端显示真实的错误码，并提供重试入口；BFF 和前端都不回退示例数据。
- 新的错误码需要登记在 `contracts/openapi/bff.yaml` 的错误码说明中（:12-13）。

## R12：开发态测试资产标识（FR-016、FR-017）

- **Decision**：
  - **标识方式**：使用一个专用的 OM 分类及其下的一个标签，显示名为「开发态测试元数据」，贴在导入工具创建的每个库、Schema、表上，以及术语表、术语上。分类和标签的英文名在实施时定为常量，例如 `ContextureDevTest.DevTestMetadata`。
    - 这个标签进入 `tags.tagFQN`，也在搜索结果的 `_source` 中，所以卡片和摘要不需要额外请求就能显示来源（FR-011「来源标识」）。
    - 没有这个标签的资产显示为「真实采集来源」。
  - **服务不带连接**：导入工具创建的 `DatabaseService` 只有 `name`、`serviceType`、`description`，不写连接信息。OM 允许这样创建（`$SVC/resources/services/ServiceEntityResource.java:59,95`；`ServiceEntityRepository.java:157`）。因此它在 005 数据源管理中会如实显示为「待配置」，不会表现为已连通的源库（FR-017）。服务描述中写明「开发态测试元数据，由 testdata 导入工具生成」。
- **Rationale**：
  - `databaseService` 没有 `extension` 属性，无法挂自定义属性。表的 `extension` 在搜索映射中是 `enabled:false`，不能直接用于筛选。
  - `provider` 只存在于术语、标签、分类上。
  - 标签是唯一一个在全部所需实体上都可用、被索引、可筛选、也可展示的原生字段（`$SVC/search/indexes/TableIndex.java:18-30`、`SearchIndex.java:232`）。
  - 不新增实体（宪法 VII）。
- **影响**：
  - 这个标签会出现在「分类标签」筛选项和标签列表中。这是 OM 中的真实数据，如实显示即可，也方便用户用筛选排除测试数据。
  - 导入的服务会出现在 005 数据源列表中，状态为「待配置」。这两点都写进 `acceptance.md`。
- **Alternatives considered**：
  - 按服务名前缀识别：依赖命名约定，用户也能建同名服务，不可靠，否决。
  - 表的自定义属性：服务上挂不了，表的属性不能直接筛选，否决。
  - `sourceUrl`：服务上没有这个字段，否决。

## R13：导入工具的幂等、范围与撤除（FR-016、FR-017）

- **位置与入口**：在 `testdata/mockfactory` 中新增子命令 `python -m mockfactory om-import`。它复用 003 的表定义（`mockfactory/schema/{mes,qms,dw}.py`，Python dataclass，表和字段都有中文注释），不另起数据源。Makefile 增加 `make dev-metadata` 和 `make dev-metadata-remove` 两个目标。
- **生成内容**：
  - **服务**：由 003 的 MES、QMS、数仓三套定义各生成一个开发态服务（不带连接，见 R12），服务名固定、带工具专用前缀；其下生成库、Schema 和表。字段的中文说明写入 `description`；表名、字段名使用 003 的英文名。
  - **同名表**：003 的表名在各系统中是否已有重名，实施时检查。没有的话，在另一个 Schema 下生成一张同名表。
  - **治理样例**：工具自己的术语表与若干术语、一个业务域、一个分类与若干标签，分级使用 OM 自带的 `Tier.*`。负责人使用已有的 OM 团队 `admin` / `ai-engineer`（由 `tools/om_config.py` 创建），不新建用户。
  - **覆盖面**：样例需要覆盖缺失属性（无负责人、无分级、无业务域）、组合筛选和同名表。具体分配写在 fixture 定义中，测试直接引用 fixture，不引用原型数值。
- **幂等 Decision**：
  - 全部写入用 OM 的 `PUT` createOrUpdate，按 FQN 查找，包括已软删除的实体（`$SVC/jdbi3/EntityRepository.java:3776-3790`）。
  - 工具根据响应头 `X-OpenMetadata-Change` 统计结果：201 或 `entityCreated` 记为新建，`entityUpdated` 记为更新，`entityNoChange` 记为未变化（EntityRepository.java:4222,9991-9993；`RestUtil.java:52,148-160`）。运行结束后输出三项数量。
  - 第二次运行时新建数应为 0（SC-008）。
  - 软删除的实体在 PUT 时会被恢复（:4197-4200），因此「撤除后再导入」可以正常工作。
- **只管理自己的资产**：
  - 工具只操作 fixture 中声明的 FQN。
  - 写入前检查：如果目标服务或术语表已存在、但**没有**开发态标识（R12），说明不是本工具创建的，拒绝写入并退出。这样可以避免覆盖 005 采集的资产。
  - 撤除时，只删除带开发态标识的服务（`DELETE /v1/services/databaseServices/name/{name}?hardDelete=true&recursive=true`，`DatabaseServiceResource.java:669-760`），以及工具自己的术语表、分类和业务域。
- **目标环境**：
  - 必须显式传入 `--target local`，与 003 的 `--target local|dsn` 约定一致，还要传入 OM 地址。缺少任一参数时，拒绝写入并说明原因。
  - 凭证只从环境变量读取：沿用 `tools/om_config.py:200-213` 的 provisioner 客户端凭证，或 `OM_TOKEN`，来自 `.env.local`。工具不写入任何文件，也不打印凭证。
- **为什么用这个身份**：导入是开发设施，不代表任何用户，使用 seed 已有的 provisioner 服务身份，与 `make seed` 一致。它不进入客户交付物（FR-017）。

## R14：前端路由、会话内状态与 005 改造（FR-001～FR-003、FR-015、D1）

- **路由 Decision**（React Router 7.18，现有的 `<Routes>` 写法，`apps/web/src/App.tsx`）：

  | 路径 | 视图 |
  | --- | --- |
  | `/assets` | 探索视图 |
  | `/assets/sources/*` | 005 `SourcesWorkspace` 的现有子路由整体迁入：列表、向导、`:name` 详情、任务与配置 |
  | `/assets/:entityType/:fqn` | `entityType ∈ {database, databaseSchema, table}` 时进入 005 的资产详情；`glossaryTerm`、`tag` 进入 006 的只读详情 |
  | `/sources` | 重定向到 `/assets/sources` |
  | `/sources/:name` | 重定向到 `/assets/sources/:name` |
  | `/sources/:name/assets/:type/:fqn` | 重定向到 `/assets/:type/:fqn`。`databaseService` 类型改为 `/assets/sources/:name` |

  - 静态段 `sources` 的匹配优先于动态段 `:entityType`。
  - 005 的详情路径带服务名；新路径不带，服务名从 FQN 的第一段得到（005 `splitFqn`，`format.ts:163`）。
  - `assetHref`（`format.ts:180-187`）改为生成新路径。
- **导航与外壳**：
  - `layout/navigation.ts` 中一级「资产」的路径改为 `/assets`，去掉二级的「资产搜索」「数据源」两个链接（D2）。
  - `AppShell.tsx:22` 原来在 `/sources` 下渲染 `CatalogTree`，改为在 `/assets` 下渲染浏览树或类型列表。
  - 可拖宽的二级栏（`SecondaryNav.tsx:30-132`）和 ≤850px 时的「目录」抽屉（`SourcesWorkspace.tsx:23-43`、`sources.css:635-662`）原样沿用，抽屉中换成浏览树。
  - `/assets` 不再显示 `NotOpenPage`。
- **浏览树改造**：`features/sources/CatalogTree.tsx` 改为基于 R3 的浏览树组件，移到 `features/assets/`。树的标签由「数据源目录」改为「数据资产」相关文案。
  - 点击节点由 `navigate(assetHref(...))` 改为设置位置条件。在子视图中点击时，先回到 `/assets`，再设置位置条件（FR-003）。
- **没有详情页的类型（U1 = A）**：`entityType` 不属于 database、databaseSchema、table、tableColumn、glossaryTerm、tag 的结果，卡片名称不渲染为链接，点击卡片只选中并显示摘要；点击这类输入建议时，把该资产名称填入关键词并执行搜索，不跳转。
- **顶栏面包屑（spec 界面基线第 3 条）**：按原型 `renderBreadcrumb()`（`prototype/index.html:2415`）：
  - 探索视图：「数据资产」，有位置条件时依次接上各层位置；
  - 数据源管理：「数据资产 / 数据源管理」；
  - 资产详情：「数据资产 / <服务> / <资产显示名>」。
  
  第一段「数据资产」可以点击返回探索视图（保留条件）。
- **会话内保留条件（FR-015、US3-2）**：
  - 搜索条件放在 `/assets` 布局层的 React 上下文中（`useReducer`）。子视图都在同一布局下，切换路由时条件不丢失；刷新后回到初始状态（D9，不写地址）。
  - 不引入新的状态库；数据请求沿用 react-query 5（`features/sources/queries.ts` 的配置：`retry:false`、`staleTime:0`）。
- **Q4 文案**：「重要程度（Tier）」统一改为「分级（Tier）」，同时改帮助文字中的「业务重要程度」。涉及位置：
  - `PropertyEditModal.tsx:345-346`、`AssetProperties.tsx:99`；
  - BFF 错误消息 `om_sources.py:804`；
  - e2e `tests/e2e/sources.spec.ts:312`。
  
  组件单元测试中没有断言这段文案。

## R15：中文分词与环境前置（D10、D11）

- **中文分词**：保持 EN 映射。`deploy/` 下没有设置 `ELASTICSEARCH_INDEX_MAPPING_LANG`，上游默认值为 EN（`conf/openmetadata.yaml:592`）。006 不安装 IK 插件，也不修改映射（D10）。验收时用一组固定的中文关键词实测（SC-009），关键词取自 003 表定义中的中文注释，结果记入 `acceptance.md`。
- **OpenSearch 稳定性（D11）**：开发搜索接口前先排查。当前 OpenSearch 3.4.0 为单节点，堆内存 `-Xms512m -Xmx512m`，持久卷 5Gi（`deploy/components/opensearch/values/base.yaml`）。排查重启原因（OOM、探针、磁盘），如需调整 values，只改配置。排查结论和调整写入 `acceptance.md` 的环境前置项。排查完成前，`-m cluster` 搜索集成测试的失败按「环境阻塞」如实记录。

## R16：权限与审计（FR-020）

- BFF 新路由全部使用 `require_web_context`（只允许 admin 或 ai-engineer，`api/deps.py:65-70`），以 `OmClient` 交换得到的用户委托令牌调用 OM。
- OM 的 `enableAccessControl` 默认为 `false`，`/aggregate` 和 `/entityTypeCounts` 本身也不过滤（对齐调研第 7 节）。所有登录用户看到的资产范围相同，按宪法 IV 的 Phase 1 例外处理，写入验收说明。
- 日志与追踪：沿用 `contexture_core.telemetry` 的 `bind_context` 和 JSON 日志（携带 `trace_id`、`tenant_id`）。每个搜索、摘要、详情请求输出一条结构化日志：操作、类型、关键词长度（不记录关键词原文，避免业务敏感词进入日志）、条件维度、结果数、耗时。日志不记录令牌。
- 006 全部是只读操作，不触发 005 的写审计（`audit_write`）。

## 实施中的修正（2026-11-09）

- **库与 Schema 的 `certification`**（R9）：实测 OM 接受 `fields=certification`；fixture 中未设置认证，响应不含该键。摘要沿用 R9 的字段清单。
- **高亮片段**（R8）：OM 返回的高亮片段已做 HTML 实体转义（如 `&#xff1a;`），中文在 EN 映射下按单字高亮。BFF 解析片段时先解码实体，再以纯文本片段返回。
- **卡片标题**（R8）：只命中 `name` 字段时，不能用 `name` 的高亮代替 `displayName`；只有 `displayName` 缺失或与 `name` 相同时才使用 `name` 的高亮（e2e 实测发现，已补单元测试）。
- **开发态标识**（R12）：分类（classification）实体没有 `tags` 字段，无法贴标识；导入工具改为在分类描述开头写固定前缀 `[织境开发态测试元数据]` 判断归属。其余实体仍贴标识标签。
- **导入工具**（R13）：
  - 经集群网络返回的响应头为小写 `x-openmetadata-change`，统计时按大小写不敏感读取；
  - OM 不允许删除仍有标签的分类（`HTTP 400 classification is not empty`，即使带 `recursive=true`），撤除时先删标签再删分类；
  - 导入后立即可搜到全部 29 张表（实测 0.0s）。
- **Web 构建产物路径**（R14）：Vite 默认把构建产物放在 `/assets/`，与数据资产页的 `/assets/*` 路由冲突（部署后 `/assets/sources` 为 nginx 404）。构建产物改放 `/static/`（`vite.config.ts` 的 `build.assetsDir`），nginx 对 `/static/` 设长缓存，`/assets/*` 回落到单页应用。
- **005 目录树的自动刷新**（R14）：采集运行结束时，005 原来让数据源相关缓存失效以刷新左侧目录；改为同时让数据资产页的查询失效，浏览树随之刷新（005 e2e 验证）。
- **OpenSearch 内存**（R15、D11）：lite 环境原为堆 384m、上限 1Gi，被 OOMKilled 321 次。先把上限调到 1280Mi，空载 10 分钟稳定；但完整 e2e 负载下堆接近占满（约 370MB/384MB），再次 OOMKilled。于是改为堆 512m、上限 1536Mi，完整 e2e 期间仍被 OOMKilled 1 次。同一集群中 Airflow scheduler、dag-processor 等组件也在反复 OOM，说明 lite 环境整体内存不足，已作为环境阻塞写入 acceptance.md，由负责人决定是否进一步调整。
- **接口位置**：术语与标签详情接口放在 `api/assets.py`（与摘要共用 `AssetReader` 依赖），路径与契约一致（`/bff/v1/governance/...`），plan 原写 `api/catalog.py`。
- **005 的 `governance_view` 未改用 `split_tags`**：改用会让数据级别标签从 005 的可编辑分类标签中消失，造成退化；`split_tags` 只供 006 使用。
