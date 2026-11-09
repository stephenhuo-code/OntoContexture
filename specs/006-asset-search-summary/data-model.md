# Data Model: 资产搜索与摘要（006）

**原则**：遵循宪法 VII，**不新增任何持久化实体或数据表**。资产、治理对象和搜索索引都使用 OpenMetadata 2.0.3 原生的实体与索引。BFF 只定义接口 DTO 和运行时投影，契约见 [contracts/openapi.yaml](contracts/openapi.yaml)，不持久化任何状态。BFF 本地存储仍只有 002 的 `bff_sessions`。搜索条件只保存在浏览器内存中，不写入地址，也不写入存储。

## 1. 正本（OpenMetadata 原生）

| 织境概念 | OM 实体 / 索引 | 本期使用的字段 | 说明 |
| --- | --- | --- | --- |
| 数据库类资产 | `DatabaseService`、`Database`、`DatabaseSchema`、`Table`、`StoredProcedure`；索引 `table_search_index` 等 | `id`、`name`、`displayName`、`fullyQualifiedName`、`entityType`、`serviceType`、`service`、`database`、`databaseSchema`、`description`、`owners`、`domains`、`tags`、`dataProducts`、`certification`、`tableType`、`columns`、`tableConstraints`、`totalVotes`、`updatedAt` | 来自 005 采集，或 006 导入工具写入 |
| 列 | 表实体的 `columns[]`；索引 `column_search_index`（别名 `tableColumn`） | `name`、`displayName`、`fullyQualifiedName`、`dataType`、`dataTypeDisplay`、`constraint`、`description`、`tags`、`table{id, fullyQualifiedName}` | 列在 OM 中没有独立的实体接口，摘要读取所属表（research R10） |
| 业务术语 | `GlossaryTerm`；索引 `glossary_term_search_index` | 见 research R9 的字段清单（负责人已确认） | 只读 |
| 分类标签 | `Tag`、`Classification`；索引 `tag_search_index` | 见 research R9 的字段清单（负责人已确认） | 只读 |
| 分级（Tier） | 分类 `Tier` 下的标签（`Tier.Tier1`～`Tier.Tier5`） | `tags[].tagFQN` 中以 `Tier.` 开头的项；索引字段为 `tier.tagFQN` | 显示为「分级（Tier）」 |
| 数据安全级别 | 分类「数据级别」下的标签（一级 / 二级 / 三级，ADR-0008） | `tags[].tagFQN` 中以 `数据级别.` 开头的项 | 单独一行显示；筛选沿用「分类标签」维度 |
| 认证 | 实体的 `certification` 字段 | `certification.tagLabel.tagFQN` | 以徽章显示 |
| 开发态测试标识 | 导入工具专用分类下的一个标签（research R12） | `tags[].tagFQN` | 判断卡片来源；没有该标签即为「真实采集来源」 |
| 搜索设置 | `/v1/system/settings/searchSettings` | — | 006 不修改，使用默认值 |

## 2. 搜索条件 `SearchCriteria`（请求 DTO，只在会话内保留）

| 字段 | 类型 | 校验规则 | 来源 |
| --- | --- | --- | --- |
| `keyword` | string | 去掉首尾空白，长度 ≤ 200；空串表示无关键词 | FR-004 |
| `scope` | `EntityType` 或 null | 白名单，见第 5 节；null 表示搜索全部 | FR-004、D4 |
| `entityType` | `EntityType` 或 null | 白名单；有关键词时表示左栏选中的类型 | FR-007 |
| `browsePath` | `BrowseStep[]` | 第一项必须是 `root`；各层按固定顺序排列，不得跳层；最多 6 层 | FR-006、FR-009 |
| `filters` | `FacetDimension` → `{values: string[], includeNone: boolean}` | 维度取白名单；仅表类型可用的维度只能在 `entityType=table` 时使用；`includeNone` 只用于支持「无」的维度；每个维度最多 50 个取值 | FR-008 |
| `sort` | `{field: popularity \| name \| relevance \| updatedAt, order: asc \| desc}` | 默认 `popularity` / `desc` | FR-010 |
| `page`、`pageSize` | int | `page ≥ 1`；`pageSize ∈ {15, 25, 50}`；`(page-1)×pageSize + pageSize ≤ 10000` | FR-010、research R6 |

- `BrowseStep = {level, value, label}`。`level` 依次为 `root`、`serviceType`、`service`、`database`、`databaseSchema`、`entityType`；`root` 的取值为大类键，例如 `databases`、`governance`。治理大类的路径是 `root → entityType`。
- `scope` 与 `entityType` 同时存在时，二者必须相同；否则返回 `422 search.invalid_criteria`。
- 前端规则：
  - 改变关键词、范围、位置或筛选时，页码回到 1；改变排序时，页码也回到 1（FR-010）。
  - 「清除全部」会清空关键词、位置和筛选（US2-5）。
  - 删除某一层位置条件时，连同下层一起删除。

## 3. 投影（运行时计算，不持久化）

| 投影 | 来源 | 规则 |
| --- | --- | --- |
| `AssetRef`（统一身份） | 搜索命中的 `_source` | `{entityType, id, fqn}`。列表、摘要和详情都使用同一个身份 |
| `SearchHit`（卡片） | `/search/query` 的 `hits[]` | 内容包括：身份；`name` / `displayName`；`breadcrumb`（服务 / 库 / Schema 的显示名）；`description`；`highlights`（片段数组，research R8）；`domains`；`owners`；`tier`；`dataLevel`；`certification`；`matchedFields`（`[{field, count}]`）；`origin`（`collected` 或 `devTest`，按 research R12 的标签判断）；`serviceType`。列命中还有 `parentTable {id, fqn}` 和 `columnName` |
| `SearchPage` | 同上 | `total`（`hits.total.value`）、`page`、`pageSize`、`windowLimited`（总数是否超过 10000） |
| `TypeCount` | `/entityTypeCounts`，另加一次 `size=1` 的首条命中查询 | `[{entityType, count}]`，只保留计数大于 0 的类型；另返回 `topHitType`。默认选中的类型：`topHitType` 的计数大于 0 时选它，否则选计数最多的类型（FR-007） |
| `FacetOption` | `/search/aggregate` 的桶 | `{value, label, count}`：`value` 取桶键；`label` 取 top_hits 中的原始显示名，没有时用 `value`。选项按 OM 返回的顺序排列。「无」不是选项，由前端固定显示，没有计数（research R4） |
| `BrowseNode` | `/search/aggregate` 的桶 | `{level, value, label, count, hasChildren}`：计数为 0 的根节点不返回；`entityType` 层的 `hasChildren` 为 false |
| `Suggestion` | `/search/query`（`size=15`） | 按 `entityType` 分组，每组最多 5 条；每条为 `{ref, label, fqn}`，列还带 `parentTable` |
| `AssetSummary` | 实体的 `/name/{fqn}` 接口（research R9） | 内容包括：身份；概览各项（描述、负责人、业务域、分级、数据安全级别、认证、业务术语、分类标签、数据产品、来源）；表另有 `columns[]`（名称、数据类型、约束（主键 / 唯一）、描述、分类标签）；列另有 `column`（同上）和 `parentTable` |
| `GlossaryTermDetail` / `TagDetail` | `/glossaryTerms/name/{fqn}`、`/tags/name/{fqn}` | 只含 research R9 中负责人已确认的原生字段；没有任何编辑字段 |

**`tags` 的拆分规则**（`AssetSummary`、`SearchHit` 共用，复用 005 `governance_view` 的识别方式）：

1. `tagFQN` 以 `Tier.` 开头 → 分级；
2. 以 `数据级别.` 开头 → 数据安全级别；
3. 等于开发态标识标签的 FQN → 来源标识（不再作为普通分类标签显示）；
4. `source = Glossary` → 业务术语；
5. 其余 → 分类标签。

## 4. 状态转移（前端探索视图）

```text
初始（无关键词，显示浏览树）──回车搜索──▶ 有关键词（显示类型列表，排序改为相关性）
       ▲                                   │
       └──────── 清除全部 / 清空关键词 ──────┘
任意状态 ──请求中──▶ 加载中 ──▶ 有结果 | 无结果 | 出错（显示错误码，可重试） | 零资产
有结果 ──自动选中第一条──▶ 摘要打开 ──Esc、关闭或无结果──▶ 摘要关闭
探索视图 ──进入子视图（详情 / 数据源管理）──▶ 子视图 ──返回，或点击浏览树──▶ 探索视图（保留条件；点击浏览树时以该节点作为位置条件）
```

## 5. 白名单

- **`EntityType`**：`dataAsset` 别名覆盖的 24 类实体（`$SPEC/elasticsearch/indexMapping.json`，已逐项核对，清单见契约 `EntityType`）。Phase 1 会实际出现的有 `table`、`tableColumn`、`database`、`databaseSchema`、`storedProcedure`、`glossaryTerm`、`tag`、`metric`、`dataProduct`。服务（`databaseService`）不在 `dataAsset` 中，不会出现在结果里，只作为浏览树的一层和卡片位置。
- **`FacetDimension`**：
  - 通用：`entityType`、`domain`、`dataProduct`、`owner`、`tag`、`tier`、`service`、`serviceType`、`certification`；
  - 仅表类型：`database`、`databaseSchema`、`column`、`tableType`、`columnDescriptionStatus`；
  - 字段映射见 research R4。
- **支持「无」的维度**：`owner`、`domain`、`tier`、`tag`、`certification`。

## 6. 开发态导入 fixture（testdata，不进入交付物）

| 项 | 规则 |
| --- | --- |
| 来源 | 003 的 `mockfactory/schema/{mes,qms,dw}.py` 表定义；中文注释写入 `description` |
| 命名 | 服务名使用固定的工具前缀；术语表、分类、业务域的名称为工具常量 |
| 标识 | 每个库、Schema、表、术语表、术语都贴开发态标识标签；服务不带连接，描述中注明是开发态测试数据 |
| 样例覆盖 | 同名表（不同 Schema）、缺负责人、缺分级、缺业务域、多维组合（业务域 × 分级 × 标签）、带数据级别标签的字段 |
| 结果统计 | 按 `X-OpenMetadata-Change` 统计新建、更新、未变化的数量 |
| 撤除 | 只删除带标识的自有服务（hard delete，recursive）以及自有的术语表、分类、业务域 |
