---

description: "006 资产搜索与摘要的实施任务清单"
---

# Tasks: 资产搜索与摘要（Asset Search & Summary）

**Input**：`specs/006-asset-search-summary/` 下的 plan.md、spec.md、research.md（R1–R16）、data-model.md、contracts/openapi.yaml、quickstart.md

**Tests**：本特性按宪法 I 强制测试先行。每个实现任务之前都有对应的失败测试任务（Red）。提交顺序为「测试提交 → 实现提交」，PR 中保留这个历史，不 squash。

**通用约束**（适用于全部任务）：
- 不新增服务、表、持久化状态或运行时依赖。
- 不修改 OM 的 searchSettings、索引映射或插件，不打补丁。
- 不引入 spec 和 plan 之外的概念、字段或选项。
- 不做以下内容：URL 状态（D9）、高级搜索、导出、显示已删除（D5）、血缘页签（D6）、摘要内编辑、向量化。
- 集成测试（`-m cluster`）使用真实的 OM 和 OpenSearch。`om_fake` 只用于单元测试和契约测试。
- 断言依据导入工具的 fixture 或 OM 实际数据，不使用原型中的数值。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可以并行（文件不同，不依赖未完成的任务）
- **[Story]**：所属用户故事（US1 / US2 / US3）
- 每个任务都写明文件路径、对应的需求编号和完成判定

---

## Phase 1: Setup（阶段 A 环境前置）

**Purpose**：确认搜索验收所依赖的 OpenSearch 是稳定的（D11、research R15）。

- [x] T001 排查本地 OpenSearch 反复重启的原因。
  - 记录重启次数基线：`kubectl -n contexture get pod opensearch-cluster-master-0 -o jsonpath='{.status.containerStatuses[0].restartCount}'`。
  - 执行 `kubectl -n contexture describe pod opensearch-cluster-master-0` 与 `kubectl -n contexture logs opensearch-cluster-master-0 --previous`，判断原因：OOMKilled、探针失败或磁盘。
  - 把结论写入 `specs/006-asset-search-summary/acceptance.md` 草稿的「环境前置」一节。
  - 对应：D11、Assumptions「环境前置」。
  - 完成判定：草稿中有原因结论和基线次数。
- [x] T002 如果 T001 确认是配置原因，只调整 `deploy/components/opensearch/values/base.yaml`、`local.yaml`、`lite.yaml` 中对应的值（例如堆内存、探针、存储），不改其他组件。
  - 改完运行 `make components-check`，再执行 `make up` 并观察 10 分钟。
  - 对应：D11、宪法 VI（只改配置）。
  - 完成判定（闸门）：10 分钟内重启次数不增长。
  - 如果仍未解决，在 acceptance 草稿中记为「环境阻塞」，开发继续进行。
- [x] T003 [P] 记录开工前的基线：运行 `make lint`、`make test`、`pnpm --filter @contexture/web test`，把结果写入 acceptance 草稿。
  - 对应：SC-007（005 不退化的对照基线）。
  - 完成判定：基线结果已记录。

---

## Phase 2: Foundational（阶段 B 测试数据、阶段 C 契约、BFF 与 Web 公共基础）

**Purpose**：所有用户故事共用的前置工作。**本阶段完成前不开始任何用户故事。**

### B. 开发态元数据导入工具（FR-016、FR-017、SC-008；research R12、R13）

- [x] T004 [P] 编写失败测试 `testdata/tests/test_om_import_fixture.py`，覆盖以下要求：
  - fixture 由 `testdata/mockfactory/schema/{mes,qms,dw}.py` 生成；
  - 每张表和每个字段的 `description` 都等于 003 定义中的中文注释；
  - 服务只包含 `name`、`serviceType`、`description`，**不带 `connection`**，描述中注明「开发态测试元数据，由 testdata 导入工具生成」；
  - 每个库、Schema、表、术语表、术语都带有开发态标识标签（data-model 第 6 节）；
  - 样例至少覆盖：同名表（位于不同 Schema）、缺负责人、缺分级、缺业务域、业务域 × 分级 × 标签的组合、带「数据级别.*」标签的字段、无 `displayName` 的实体；
  - 负责人只使用现有的 OM 团队 `admin` 或 `ai-engineer`。
  - 完成判定：测试运行失败，原因是模块不存在。
- [x] T005 [P] 编写失败测试 `testdata/tests/test_om_import_cli.py`。用 `httpx.MockTransport` 模拟 OM，覆盖以下要求：
  - 缺少 `--target local` 时，退出码非 0，且没有发出任何 HTTP 请求；
  - 凭证只从环境变量读取（`OM_TOKEN`，或 `KEYCLOAK_PROVISIONER_CLIENT_ID` / `KEYCLOAK_PROVISIONER_CLIENT_SECRET`）；输出中不出现令牌；
  - 全部写入都使用 `PUT`；
  - 按响应头 `X-OpenMetadata-Change` 统计：201 或 `entityCreated` 记为「新建」，`entityUpdated` 记为「更新」，`entityNoChange` 记为「未变化」，并输出这三项数量；
  - 目标服务或术语表已经存在、但没有开发态标识时，拒绝写入并退出；
  - `--remove` 只删除带标识的自有服务（`DELETE /v1/services/databaseServices/name/{name}?hardDelete=true&recursive=true`），以及自有的术语表、分类和业务域。
  - 完成判定：测试运行失败。
- [x] T006 实现 fixture 模块 `testdata/mockfactory/om_import/fixture.py`。
  - 工具用到的名称定义为常量：服务名前缀、开发态分类与标签的名称（显示名为「开发态测试元数据」）、术语表、业务域、样例分类。
  - 分级使用 OM 自带的 `Tier.*` 标签。
  - 对应：FR-016、research R12、R13。
  - 完成判定：T004 通过。
- [x] T007 实现写入与撤除模块 `testdata/mockfactory/om_import/writer.py`。
  - 写入顺序：分类 → 标签 → 业务域 → 术语表 → 术语 → 服务 → 库 → Schema → 表。
  - 写入前做自有资产检查（见 T005）；完成后输出统计结果；支持撤除。
  - 对应：FR-016、FR-017。
  - 完成判定：T005 中与写入相关的用例通过。
- [x] T008 在 `testdata/mockfactory/__main__.py` 中注册 `om-import` 子命令。
  - 参数：`--target local`（必填）、`--om-url`（必填）、`--remove`。
  - 对应：FR-017。
  - 完成判定：T005 全部通过。
- [x] T009 在根目录 `Makefile` 中新增 `dev-metadata` 与 `dev-metadata-remove` 两个目标。
  - 参照 `seed` 目标的做法：加载 `.env.local`、设置 Caddy CA、端口转发 `svc/openmetadata` 8585。
  - 调用 `uv run python -m mockfactory om-import --target local --om-url http://localhost:8585`，撤除时再加 `--remove`。
  - 对应：quickstart 第 1 节。
  - 完成判定：`make dev-metadata` 可以执行。
- [x] T010 编写集成测试 `testdata/tests/cluster/test_om_import_cluster.py`（`-m cluster`），覆盖以下要求：
  - 连续导入两次，第二次「新建」为 0，测试资产总数不变；
  - 005 服务 `mock-mes`（如果存在）的 `version` 与 `updatedAt` 不变；
  - 导入后立即可以通过 OM `/v1/search/query?index=table` 按表名搜到；
  - 撤除后搜不到，再次导入成功（PUT 会恢复已软删除的实体）；
  - 观察「写入后短暂搜不到」（spec 边界情况）：导入完成后轮询 OM `/v1/search/query`，记录每张表从写入完成到能搜到的耗时，以及是否出现过搜不到；结论写入 acceptance 草稿。
  - 对应：SC-008、FR-016、FR-017。
  - 完成判定：在集群上通过；环境阻塞时记录原因。

### C. 契约（FR-019；plan「契约与先行测试」）

- [x] T011 把 `specs/006-asset-search-summary/contracts/openapi.yaml` 合入 `contracts/openapi/bff.yaml`：
  - 合入 8 个路径和 17 个 schema；
  - `info.version` 从 0.2.0 改为 0.3.0；
  - 在 `info.description` 中登记 `search.invalid_criteria`、`search.window_exceeded`、`search.index_missing`、`search.timeout`；
  - 复用已有的 `Ref` 和 `components/responses`；
  - 不修改已有接口。
  - 完成判定：`uv run pytest services/bff/tests/contract/test_contract.py` 能加载契约。新路径还没有实现，Schemathesis 对新路径的用例失败，属于预期。
- [x] T012 运行 `pnpm --filter @contexture/ts-api generate` 生成 `packages/ts-api/src/bff.d.ts`，在 `packages/ts-api/src/index.ts` 中导出新的类型：`SearchCriteria`、`SearchPage`、`SearchHit`、`TypeCounts`、`FacetOption`、`BrowseNode`、`Suggestion`、`AssetSummary`、`GlossaryTermDetail`、`TagDetail`。
  - 完成判定：`pnpm --filter @contexture/ts-api check` 通过。

### BFF 公共基础

- [x] T013 [P] 扩展 `services/bff/tests/om_fake.py`，增加以下内存模拟：
  - `GET /v1/search/query`、`/v1/search/entityTypeCounts`、`/v1/search/aggregate`：返回 OpenSearch 的原始结构，聚合键带 `sterms#` 前缀，高亮使用 `<span class="text-highlighter">`；
  - `GET /v1/glossaryTerms/name/{fqn}`、`/v1/tags/name/{fqn}`；
  - 故障注入：500 `{"code":500,"message":"Failed to find index x"}`、`timed_out:true`、连接错误。
  
  这个模拟只用于单元测试和契约测试。
  - 完成判定：已有测试全部仍然通过。
- [x] T014 [P] 编写失败测试 `services/bff/tests/unit/test_tag_split.py`，按 data-model 第 3 节的规则 1–5 拆分 `tags`：
  - `Tier.` 开头 → 分级；
  - `数据级别.` 开头 → 数据安全级别；
  - 等于开发态标识 FQN → 来源标识（不出现在分类标签中）；
  - `source=Glossary` → 业务术语；
  - 其余 → 分类标签。
  - 对应：FR-014。
  - 完成判定：测试失败。
- [x] T015 在 `services/bff/src/contexture_bff/adapters/om_sources.py` 中，从 `governance_view` 抽出可复用的 `split_tags()`，让 005 的代码改为调用它，并增加对数据级别和开发态标识的识别。
  - 完成判定：T014 通过，005 已有的单元测试和契约测试全部通过。
- [x] T016 [P] 编写失败测试 `services/bff/tests/unit/test_om_search_errors.py`，覆盖以下映射：
  - OM 返回 500，且消息以 `Failed to find index` 开头 → `503 search.index_missing`；
  - 响应中 `timed_out=true` → `504 search.timeout`，不返回部分结果；
  - 其他 5xx 或网络错误 → `502 upstream.unavailable`；
  - 错误体符合 `contracts/schemas/error.json`。
  
  同时在 `services/bff/tests/unit/test_om_client.py` 中补充用例：5xx 时，OM 返回的消息要传到异常的 `details` 中。
  - 对应：research R11。
  - 完成判定：测试失败。
- [x] T017 实现上述错误映射：
  - 修改 `services/bff/src/contexture_bff/adapters/om_client.py`：5xx 时在 `details` 中保留 OM 的 `message`，保持原有错误码不变；
  - 新建 `services/bff/src/contexture_bff/adapters/om_search.py`，实现 `_raise_for_search()`，负责识别索引缺失和超时。
  - 完成判定：T016 通过，005 已有测试全部通过。

### Web 公共基础（路由、导航、会话内条件；D1、D2、FR-001～FR-003、FR-015）

- [x] T018 先修改受影响的 005 Web 单元测试断言（Red）：
  - `apps/web/src/__tests__/navigation.test.tsx:70-71,137-157,186`：一级「资产」指向 `/assets`；二级栏不再有「资产搜索」「数据源」链接。
  - `shell-pages.test.tsx:32`：`/assets` 不再显示「尚未开放」。
  - 以下测试中挂载的路由由 `/sources/*` 改为 `/assets/sources/*`，资产详情地址改为 `/assets/:entityType/:fqn`：
    - `catalog.test.tsx`；
    - `source-wizard.test.tsx:27-29`；
    - `source-tasks.test.tsx`；
    - `sources-list.test.tsx:11-15`；
    - `property-edit.test.tsx:174-177`；
    - `session.test.tsx:192`。
  - `catalog.test.tsx` 中树名「数据源目录」（:201,375,380,443,493）的断言，改为浏览树新的 aria 标签。
  - `shell-pages.test.tsx`：保留或补上「非 `/assets` 页面不显示搜索框」的断言（D3）。
  - 逐个核对 `login-page.test.tsx:42-46` 和 `api.test.ts:50` 中 `/assets?q=…` 这类 returnTo 示例，只在它们因路由改动而失败时才修改。
  - 完成判定：上述测试失败，原因是新路由尚未实现。
- [x] T019 [P] 编写失败测试 `apps/web/src/__tests__/assets-routing.test.tsx`，覆盖以下重定向（research R14）：
  - `/sources` → `/assets/sources`；
  - `/sources/:name` → `/assets/sources/:name`；
  - `/sources/:name/assets/table/:fqn` → `/assets/table/:fqn`；
  - `/sources/:name/assets/databaseService/:fqn` → `/assets/sources/:name`；
  - `/assets/sources` 由 `SourcesWorkspace` 渲染，不会被 `/assets/:entityType/:fqn` 匹配。
  - 完成判定：测试失败。
- [x] T020 [P] 修改 e2e 断言（Red，集群就绪后运行）：
  - `tests/e2e/shell-navigation.spec.ts:28-42,114-115,149`；
  - `tests/e2e/sources.spec.ts` 中的资产地址（:319,331,552）、树（:103,242）、抽屉（:573）；
  - `tests/e2e/sources-perf.spec.ts:75`。
  
  全部改为新路径和新的树标签。
  - 完成判定：在旧实现上运行这些断言会失败。
- [x] T021 实现新的路由：
  - 修改 `apps/web/src/App.tsx`：增加 `/assets`、`/assets/sources/*`、`/assets/:entityType/:fqn` 三条路由，以及 `/sources/*` 的重定向；`/assets` 不再使用 `NotOpenPage`。
  - 修改 `apps/web/src/features/sources/SourcesWorkspace.tsx`：路由基准改为 `/assets/sources`；保存后跳转（:77）改到新路径。
  - 修改 `apps/web/src/features/sources/format.ts:180-187` 的 `assetHref`，生成新路径。服务名从 FQN 第一段取得（`splitFqn`）。
  - 完成判定：T019 通过，T018 中与路由相关的用例通过。
- [x] T022 修改导航和外壳：
  - `apps/web/src/layout/navigation.ts`：一级「资产」的路径改为 `/assets`，删除 `asset-search`、`sources` 两个二级项，同步修改 `routePresentation`。
  - `apps/web/src/layout/SecondaryNav.tsx`：调整当前项的判断（:71）和图标映射（:22-27）；拖宽功能保持不变。
  - `apps/web/src/layout/AppShell.tsx:22`：在 `/assets` 下渲染资产左栏的占位（浏览树和类型列表在后续故事中填入）。
  - `apps/web/src/i18n/zh-CN.ts`：增加所需文案。
  - 完成判定：T018 全部通过。
- [x] T023 [P] 编写失败测试 `apps/web/src/__tests__/assets-criteria.test.tsx`，验证搜索条件的 reducer 与上下文（data-model 第 2 节）：
  - 改变关键词、范围、位置或筛选时，`page` 回到 1；改变排序时，`page` 也回到 1。
  - 「清除全部」后，关键词、位置、筛选都清空。
  - 删除某一层位置条件时，连同下层一起删除。
  - `browsePath` 的第一项必须是 `root`，不能跳层，最多 6 层。
  - `pageSize ∈ {15, 25, 50}`；`(page-1)×pageSize + pageSize ≤ 10000`。
  - 在 `/assets` 布局内切换子路由后，条件仍然保留。
  - `location.search` 始终为空，即不写入地址（D9）。
  - 完成判定：测试失败。
- [x] T024 实现 `apps/web/src/features/assets/AssetsLayout.tsx` 与 `criteria.ts`（`useReducer` 加上下文），以及 `apps/web/src/features/assets/api.ts`、`queries.ts`。
  - `api.ts` 基于 `@contexture/ts-api` 客户端。
  - react-query 的配置与 005 相同：`retry:false`、`refetchOnWindowFocus:false`、`staleTime:0`。
  - 完成判定：T023 通过。

**Checkpoint**：导入工具可用，契约已合入，005 的 Web 单元测试在新路径下全部通过。可以进入用户故事阶段。

---

## Phase 3: User Story 1 - 用关键词搜索资产并查看摘要（Priority: P1）🎯 MVP

**Goal**：用户在顶栏搜索，通过建议直接进入资产，或回车得到按相关性排序的结果；左栏显示类型列表；系统自动选中第一条结果并显示只读摘要（概览、Schema）。

**Independent Test**：执行 `make dev-metadata` 后，在 `/assets` 按表名、字段名、描述中的词搜索。逐项核对结果、类型计数、高亮、来源标识、摘要，都与 OM 实体一致（quickstart 第 2 节）。Foundational + US1 阶段只验证有关键词的路径；无关键词时的浏览树由 US2 提供。

### Tests for User Story 1 ⚠️（先写，确认失败）

- [x] T025 [P] [US1] 编写契约测试 `services/bff/tests/contract/test_assets_search_contract.py`，使用 `contract_helpers.check` 与 `om_fake`。
  - `searchAssets`：
    - 200 的响应符合 `SearchPage`；
    - 以下请求返回 422 `search.invalid_criteria`：`pageSize=20`、`scope≠entityType`、维度不在白名单内、在非表类型下使用仅表类型可用的维度、`keyword` 超过 200 字符；
    - `page=668,pageSize=15` 返回 422 `search.window_exceeded`；
    - OM 返回 500「Failed to find index」时返回 503；`timed_out` 时返回 504；OM 不可达时返回 502。
  - `countAssetTypes`：`counts` 中没有计数为 0 的项；`defaultType` 在 `topHitType` 计数大于 0 时等于它，否则等于计数最多的类型。
  - `suggestAssets`：每组 `items` 不超过 5 条；列的建议项带有 `parentTable`。
  - 对应：FR-004、FR-005、FR-007、FR-019。
  - 完成判定：测试失败（404）。
- [x] T026 [P] [US1] 编写契约测试 `services/bff/tests/contract/test_asset_summary_contract.py`，验证 `getAssetSummary`：
  - table 有 `columns`；
  - tableColumn 有 `column` 与 `parentTable`；
  - glossaryTerm 返回 200；
  - FQN 不存在时返回 `404 catalog.not_found`。
  - 对应：FR-012。
  - 完成判定：测试失败。
- [x] T027 [P] [US1] 编写单元测试 `services/bff/tests/unit/test_search_criteria.py`，验证条件翻译（research R2、R5）：
  - **关键词**：
    - 去掉首尾空白，长度不超过 200，空串转为 `*`；
    - 转义这些保留字符：`+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /`；
    - 单独出现的大写 `AND`、`OR`、`NOT` 改为小写。
  - **index**：
    - 按 `entityType` → `scope` → `dataAsset` 的优先级选取；
    - `table` 对应别名 `table`；
    - 白名单为契约 `EntityType` 中的 24 类。
  - **query_filter**：
    - 始终包含 `term deleted=false`；
    - 每次请求都带 `deleted=false` 和 `track_total_hits=true`。
  - **排序映射**：`popularity` → `totalVotes`，`name` → `displayName.keyword`，`relevance` → `_score`，`updatedAt` → `updatedAt`；默认 `desc`。
  - **分页**：`from=(page-1)×pageSize`；超过结果窗口时报错。
  - 完成判定：测试失败。
- [x] T028 [P] [US1] 编写单元测试 `services/bff/tests/unit/test_search_projection.py`，验证结果投影（research R8、R10；data-model 第 3 节）：
  - **高亮**：解析为 `TextSegment[]`，只有 `text-highlighter` 片段的 `match` 为 true；原文中的 `<script>` 等内容按普通文本保留，不作为 HTML 输出。
  - **命中字段**：`matchedFields` 不统计含 `.ngram` 的键，也不统计 `table_name`、`topic_name`、`dashboard_name`、`pipeline_name`；计数为每个键的片段数。
  - **来源**：带开发态标识的为 `origin=devTest`，否则为 `collected`。
  - **位置**：`breadcrumb` 依次为服务、库、Schema 的显示名。
  - **列**：列命中的 `parentTable` 取自 `table.fullyQualifiedName`，`columnName` 取列名。
  - **总数**：`windowLimited` 在总数超过 10000 时为 true。
  - **建议**：按 `entityType` 分组，每组最多 5 条。
  - **类型计数**：`/entityTypeCounts` 的 `query_filter` 中包含 `deleted=false`。
  - 完成判定：测试失败。
- [x] T029 [P] [US1] 编写单元测试 `services/bff/tests/unit/test_asset_summary.py`，验证摘要读取（research R9、R10）：
  - 各类型请求的 `fields`：
    - table：`owners,domains,tags,dataProducts,columns,tableConstraints,certification`；
    - database、databaseSchema：`owners,domains,tags,dataProducts,certification`；
    - glossaryTerm：`owners,domains,tags,reviewers`；
    - tag：`owners,domains,reviewers`；
    - 其他类型：`owners,domains,tags`。
  - tableColumn 读取所属表的实体，再从中取出该列。
  - 列约束合并 `column.constraint` 与 `tableConstraints`（主键、唯一）。
  - 返回 OM 实体中的 `id`。
  - OM 返回 404 时映射为 `catalog.not_found`。
  - 完成判定：测试失败。

### Implementation for User Story 1

- [x] T030 [US1] 在 `services/bff/src/contexture_bff/adapters/om_search.py` 中实现以下内容：
  - Pydantic 模型 `SearchCriteria`，字段约束与契约一致；
  - 条件翻译；
  - `search()`；
  - `type_counts()`：调用 `/entityTypeCounts`，同时调用一次 `size=1`、`include_source_fields=entityType` 的首条命中查询，两者并行；
  - `suggestions()`：`size=15`，`include_source_fields` 只取 `id,name,displayName,fullyQualifiedName,entityType,serviceType,service.displayName`，按类型分组、每组最多 5 条；
  - 投影函数。
  
  复用 `OmClient` 与 `split_tags()`。
  - 对应：FR-004、FR-005、FR-007、FR-011、FR-018、FR-019。
  - 完成判定：T027、T028 通过。
- [x] T031 [US1] 新建 `services/bff/src/contexture_bff/adapters/om_assets.py`，实现 `summary(entityType, fqn)`，包括列到所属表的处理。
  - 对应：FR-012、FR-014。
  - 完成判定：T029 通过。
- [x] T032 [US1] 新建 `services/bff/src/contexture_bff/api/assets.py`，提供四个路由：`POST /bff/v1/assets/search`、`POST /bff/v1/assets/type-counts`、`GET /bff/v1/assets/suggestions`、`GET /bff/v1/assets/summary/{entityType}/{fqn}`。
  - 全部使用 `require_web_context`。
  - 在 `services/bff/src/contexture_bff/main.py` 中挂载这些路由，在 `Services` 中注入适配器，与 sources 共用同一个 `OmClient`。
  - 对应：FR-020（鉴权部分）。
  - 完成判定：T025、T026 通过，Schemathesis 对新路径通过。
- [x] T033 [P] [US1] 编写组件测试 `apps/web/src/__tests__/assets-search.test.tsx`，使用 vitest 的假定时器。测试数据由测试内的构造函数生成，不使用原型数值。覆盖：
  - **防抖**：输入停顿 400ms 后才请求建议；新输入会取消旧请求。
  - **搜索范围**：选项来自 `keyword` 为空时的 type-counts，只列有数据的类型；默认不选，即搜索全部。
  - **回车**：排序改为「相关性」。
  - **建议**：按类型分组，每组最多 5 条，每条显示名称与位置。
  - **点击建议**：
    - table → `/assets/table/<fqn>`；
    - 列 → 所属表的详情，并通过 `location.state` 带上列名；
    - 术语、标签 → 各自的详情页；
    - 其他没有详情页的类型（如 metric）→ 把该资产名称填入关键词并执行搜索，不跳转（U1）。
  - 对应：FR-004、FR-005、FR-012。
  - 完成判定：测试失败。
- [x] T034 [P] [US1] 编写组件测试 `apps/web/src/__tests__/assets-results.test.tsx`，覆盖：
  - **TypeList**：只列计数大于 0 的类型，按 `defaultType` 默认选中；切换类型时只刷新列表。
  - **ResultCard**：
    - 显示位置面包屑、资产类型图标和名称；名称只对库、Schema、表、列、术语、标签渲染为链接，其他类型不是链接，点击卡片只选中（U1）；
    - 有认证时显示认证徽章；
    - 描述按高亮片段渲染；
    - 业务域、负责人、「分级（Tier）」、「数据安全级别」分开显示；
    - 显示命中字段统计；
    - 来源显示为「开发态测试元数据」或「真实采集来源」。
  - **SummaryPanel**：
    - 结果更新后自动选中第一条，Esc 和关闭按钮都能关闭；
    - 页签只有「概览」「Schema」；
    - 「概览」依次显示：描述、负责人、业务域、分级（Tier）、数据安全级别、认证、业务术语、分类标签、数据产品、来源；
    - 「Schema」显示名称、类型、主键或唯一约束、描述、分类标签；
    - 摘要返回的 `id` 与列表项不一致时，显示错误。
  - **无结果**：显示「无匹配结果」，提供清除条件入口，摘要关闭。
  - **顶栏面包屑**：探索视图显示「数据资产」；有位置条件时依次接上各层位置（research R14）。
  - 对应：FR-007、FR-011、FR-012、FR-014、US1 场景 2–7、spec 界面基线第 3 条。
  - 完成判定：测试失败。
- [x] T035 [US1] 实现 `apps/web/src/features/assets/` 下的 `SearchBar.tsx`（顶栏中，包括范围下拉和建议浮层）、`TypeList.tsx`、`ResultCard.tsx`、`SummaryPanel.tsx`、`ExploreView.tsx`，以及顶栏面包屑 `TopBreadcrumb.tsx`（探索视图部分，规则见 research R14），并在 `apps/web/src/i18n/zh-CN.ts` 中补充文案。
  - 所有数据都来自 BFF，没有内置示例数据，出错时不回退。
  - 完成判定：T033、T034 通过。

### 集成与实测（US1）

- [x] T036 [US1] 编写集成测试 `services/bff/tests/integration/test_assets_search_cluster.py`（`-m cluster`，前置条件为 `make dev-metadata`），覆盖：
  - fixture 中每张表都能按英文表名搜到（SC-001 的搜索部分）；
  - type-counts 与直接调用 OM `/entityTypeCounts` 的结果一致；
  - 同名表的每条结果，面包屑中的服务和 Schema 能区分开（SC-005）；
  - 含 `( ) : " AND OR NOT * ?` 的关键词不报错，结果数与去掉这些符号后的关键词一致（research R2 的验证）。
  - 完成判定：通过；环境阻塞时如实记录。
- [x] T037 [P] [US1] 编写集成实测 `services/bff/tests/integration/test_om_unconfirmed_cluster.py::test_result_window`：
  - 直接调用 OM `/search/query`，参数 `from=9995&size=15`，记录返回的状态码和消息；
  - 断言 BFF 在调用 OM 之前就返回 422。
  - 结论写入 research R6 和 acceptance 草稿。
  - 完成判定：实测结论已记录。
- [x] T038 [P] [US1] 在同一文件中编写 `test_timeout_shape`。**只在 T001、T002 闸门通过后执行**，避免冲击不稳定的本地 OpenSearch：
  - 尝试用超大 `size` 加复杂查询触发 OpenSearch 超时，记录 OM 的实际返回（`timed_out` 字段与 HTTP 状态码）；
  - 无法复现时，记录为「本地不可复现」，映射逻辑由 T016 的契约测试保证。
  - 结论写入 research R6。
  - 完成判定：已记录。
- [x] T039 [P] [US1] 在同一文件中编写 `test_certification_field`：
  - 实测 `GET /v1/databases/name/{fqn}?fields=certification` 与 `/v1/databaseSchemas/...` 是否被 OM 接受；
  - 不被接受时，从 `om_assets.py` 和 research R9 的表格中去掉 `certification`，并补充对应的单元测试断言。
  - 完成判定：已记录，代码与 research 一致。
- [x] T040 [US1] 编写集成测试 `services/bff/tests/integration/test_assets_summary_cluster.py`：
  - fixture 表的摘要（字段、约束、分级、数据级别、业务术语、分类标签、来源）与 OM 实体逐项一致；
  - 列摘要能正确取到所属表。
  - 对应：FR-012、FR-014。
  - 完成判定：通过。

**Checkpoint**：US1 可以独立演示：登录 → 搜索 → 选择资产 → 查看摘要与字段（Phase 1「006 资产业务演示」的主路径）。

---

## Phase 4: User Story 2 - 浏览树、快速筛选、条件条、排序分页（Priority: P1）

**Goal**：无关键词时，用浏览树逐层定位位置，不跳页；用快速筛选组合缩小范围（支持「无」）；条件条可以逐项删除或清除全部；结果可以排序、分页。

**Independent Test**：在 fixture 数据上依次执行：点击树节点、同一维度多选、跨维度组合、选「无」、逐层删除位置、清除全部、切换排序、切换每页条数、翻页。结果数与直接调用 OM 的结果一致（quickstart 第 3 节）。

### Tests for User Story 2 ⚠️

- [x] T041 [P] [US2] 编写契约测试 `services/bff/tests/contract/test_assets_browse_contract.py`：
  - `browseAssets`：
    - `parentPath` 为空时，返回的根节点中没有计数为 0 的项；
    - `parentPath` 跳层，或超过 `maxItems 5` 时，返回 422。
  - `getAssetFacet`：
    - `supportsNone` 只在 `owner`、`domain`、`tier`、`tag`、`certification` 上为 true；
    - `options` 中不出现「无」；
    - 在非表类型下使用 `database`、`databaseSchema`、`column`、`tableType`、`columnDescriptionStatus` 时返回 422；
    - `optionQuery` 超过 100 字符时返回 422。
  - 对应：FR-006、FR-008。
  - 完成判定：测试失败。
- [x] T042 [P] [US2] 编写单元测试 `services/bff/tests/unit/test_browse_tree.py`（research R3），覆盖：
  - **根节点**：大类清单为常量，并注明出处 `$UI/utils/SearchClassBase.ts:236-420`。
    - 数据库类包含 database、databaseSchema、storedProcedure、table、tableColumn；
    - 治理类包含 tag、glossaryTerm、metric。
  - **层级字段**：
    - 数据库类依次为 `serviceType` → `service.displayName.keyword` → `database.displayName` → `databaseSchema.displayName` → `entityType`；
    - 其他大类为 `serviceType` → `service.displayName.keyword` → `entityType`；
    - 治理类直接到 `entityType`。
  - **根节点计数**：对 `dataAsset` 聚合 `entityType.keyword`，再按大类求和。
  - **子层过滤**：
    - 父路径的每一层转成 `term`；
    - 根层另外限定该大类的子实体类型；
    - `entityType` 层使用 `entityType.keyword`，取值转小写。
  - **其他**：每层 `size=1000`；忽略 `criteria.browsePath`，以 `parentPath` 为准；`entityType` 层节点的 `hasChildren=false`。
  - 完成判定：测试失败。
- [x] T043 [P] [US2] 编写单元测试 `services/bff/tests/unit/test_facets.py`（research R4），覆盖：
  - 各维度的字段映射与 research R4 的表格逐项一致；
  - 计算某维度的选项时，`q` 的 DSL 中不包含本维度的条件，但包含关键词（`queryText`）、位置和其他维度；
  - 组合方式：同一维度内为 `bool.should`，跨维度为 `must`；`includeNone` 生成 `must_not exists`，与取值放在同一个 `should` 中；
  - `value` 参数为 `.*<转义后的输入>.*`；
  - `label` 来自 `sourceFields` 对应的 top_hits，没有时等于 `value`；
  - 默认 `size=10`；每个维度最多 50 个取值；始终带 `deleted=false`。
  - 完成判定：测试失败。

### Implementation for User Story 2

- [x] T044 [US2] 在 `services/bff/src/contexture_bff/adapters/om_search.py` 中实现 `facets()` 与 `browse()`。
  - 对应：FR-006、FR-008、FR-018。
  - 完成判定：T042、T043 通过。
- [x] T045 [US2] 在 `services/bff/src/contexture_bff/api/assets.py` 中增加 `POST /bff/v1/assets/facets` 与 `POST /bff/v1/assets/browse`。
  - 完成判定：T041 通过。
- [x] T046 [P] [US2] 编写组件测试 `apps/web/src/__tests__/assets-browse.test.tsx`，覆盖：
  - **加载与显示**：
    - 无关键词时，左栏显示浏览树；
    - 展开节点之前，不请求子层；
    - 节点显示计数；
    - 不渲染计数为 0 的根节点。
  - **点击与定位**：
    - 点击节点时只设置 `browsePath`，`location.pathname` 不变；
    - 在子视图（`/assets/table/x`）中点击节点，回到 `/assets`，并带上位置条件。
  - **有关键词**：左栏换成类型列表。
  - **窄屏**：视口不超过 850px 时，「目录」抽屉中显示浏览树。
  - 对应：FR-003、FR-006、US2 场景 1–2、US3 场景 4。
  - 完成判定：测试失败。
- [x] T047 [P] [US2] 编写组件测试 `apps/web/src/__tests__/assets-filters.test.tsx`，覆盖：
  - **QuickFilters**：
    - 不分类型时有 9 个维度：资产类型、业务域、数据产品、负责人、分类标签、分级（Tier）、服务、服务类型、认证；
    - `entityType=table` 时再增加库、Schema、列、表类型、列描述；
    - 支持选项内搜索，显示选项计数；
    - 只有 5 个维度显示「无」，且「无」没有计数。
  - **FilterChips**：
    - 位置条件按层显示，删除某一层时连同下层一起删除；
    - 每个筛选值可以单独删除；
    - 「清除全部」清空关键词、位置、筛选；
    - 无关键词且没有任何条件时，显示操作提示。
  - **排序**：选项为热度、名称、相关性、最近更新，默认热度降序；改变排序回到第 1 页。
  - **分页**：每页 15、25、50 条；`windowLimited` 时显示「仅显示前 10000 条，请缩小条件」，最大页码不超过窗口；页头显示真实的总数。
  - 对应：FR-008～FR-010、US2 场景 3–6。
  - 完成判定：测试失败。
- [x] T048 [US2] 实现以下组件：
  - `apps/web/src/features/assets/BrowseTree.tsx`：由 `features/sources/CatalogTree.tsx` 改造，展开和收起的行为沿用 005。
  - `QuickFilters.tsx`、`FilterChips.tsx`。
  - 排序与分页，放在 `ExploreView.tsx` 中。
  - 删除 `apps/web/src/features/sources/CatalogTree.tsx`，同时修改 `AppShell.tsx` 和 `SourcesWorkspace.tsx`（抽屉）中的引用。
  - 完成判定：T046、T047 通过，T018 和 005 的组件测试仍然通过。

### 集成与实测（US2）

- [x] T049 [US2] 编写集成测试 `services/bff/tests/integration/test_assets_browse_cluster.py`（`-m cluster`），覆盖：
  - **SC-004**：分别测试关键词、位置、同维度多选、跨维度组合、「无」五组用例。每组的 BFF 结果与测试中手写 DSL 直接调用 OM `/search/query` 的结果对比，总数和 ID 集合都一致。
  - **SC-001 浏览部分**：fixture 中每张表都能在浏览树对应的服务、库、Schema 节点下找到；浏览树、类型列表、筛选项的计数与直接调用 OM 的结果一致。
  - 完成判定：通过；环境阻塞时如实记录。
- [x] T050 [P] [US2] 在 `services/bff/tests/integration/test_om_unconfirmed_cluster.py` 中增加以下实测：
  - `test_display_name_fallback`：检查 fixture 中「无 displayName」实体的索引文档里 `displayName` 是否回退为 `name`，以及它在浏览树中的标签。
  - `test_database_display_name_aggregatable`：检查对 `database.displayName` 和 `databaseSchema.displayName` 做 `/aggregate` 是否返回桶。如果不返回，改用 `.keyword`，并同步修改 `om_search.py`、T042 的断言和 research R3。
  - `test_facet_option_size`：核对 OM UI 中 `optionPageSize` 的常量取值（`third_party/openmetadata/src` 的 `$UI` 目录），与 BFF 默认的 `size=10` 对齐，并更新 research R4。
  - 完成判定：三项结论都已写入 research 和 acceptance 草稿，代码与结论一致。

**Checkpoint**：US1 和 US2 都能独立工作。

---

## Phase 5: User Story 3 - 在同一页面使用数据源管理与各类资产详情（Priority: P2）

**Goal**：005 的数据源管理和资产详情作为 `/assets` 下的子视图使用；列结果可以定位到所属表；新增术语和标签的只读详情页；Tier 文案统一为「分级（Tier）」；005 功能不退化，旧链接可用。

**Independent Test**：
- 按 005 `acceptance.md` 的主要步骤，在新路径下重走一遍；
- 打开旧的 `/sources/...` 链接，确认都转到对应的新页面；
- 进入一个术语和一个标签的详情页，核对内容与 OM 一致（quickstart 第 4 节）。

### Tests for User Story 3 ⚠️

- [x] T051 [P] [US3] 编写组件测试 `apps/web/src/__tests__/assets-subviews.test.tsx`，覆盖：
  - 页头「数据源管理」进入 `/assets/sources`，「添加数据源」进入接入向导；
  - 点击卡片名称或摘要标题，进入 `/assets/{类型}/{fqn}`；库、Schema、表使用 005 的详情；
  - 从子视图返回探索视图后，关键词、位置、筛选、排序、页码都不变；
  - 在子视图中点击浏览树，回到探索视图并带上位置条件；
  - 顶栏面包屑：数据源管理显示「数据资产 / 数据源管理」，资产详情显示「数据资产 / <服务> / <资产显示名>」；点击「数据资产」返回探索视图，条件保留。
  - 对应：FR-002、FR-003、FR-015、US3 场景 1、2、4、spec 界面基线第 3 条。
  - 完成判定：测试失败。
- [x] T052 [P] [US3] 编写组件测试 `apps/web/src/__tests__/column-locate.test.tsx`，覆盖：
  - 带着 `location.state.column` 进入表详情时，滚动到该列所在行并高亮；
  - 没有这个状态时，不高亮；
  - 地址中不出现列名。
  - 对应：Q3、FR-012。
  - 完成判定：测试失败。
- [x] T053 [P] [US3] 编写契约测试 `services/bff/tests/contract/test_governance_detail_contract.py`：
  - `getGlossaryTermDetail` 与 `getTagDetail` 的 200 响应符合 schema，404 返回 `catalog.not_found`；
  - 响应中没有任何可编辑字段。
  - 对应：FR-013。
  - 完成判定：测试失败。
- [x] T054 [P] [US3] 编写单元测试 `services/bff/tests/unit/test_governance_detail.py`，按 research R9 已确认的字段清单逐项映射：
  - **术语**：名称、显示名称、FQN、所属术语表（`glossary`）、上级术语（`parent`）、描述、同义词（`synonyms`）、相关术语（`relatedTerms`）、参考链接（`references`）、负责人（`owners`）、评审人（`reviewers`）、业务域（`domains`）、分类标签（`tags`）、状态（`entityStatus`）。
  - **标签**：名称、显示名称、FQN、所属分类（`classification`）、上级标签（`parent`）、描述、负责人、评审人、业务域、是否已弃用（`deprecated`）。
  - 请求 OM 时 `fields` 必须包含：
    - 术语：`owners,reviewers,domains,tags,relatedTerms`；
    - 标签：`owners,reviewers,domains`。
  - OM 返回 404 时映射为 `catalog.not_found`。
  - 完成判定：测试失败。
- [x] T055 [P] [US3] 编写组件测试 `apps/web/src/__tests__/governance-detail.test.tsx`，覆盖：
  - 术语详情显示 14 项字段，标签详情显示 10 项字段；空值显示「—」，负责人为空时显示「未分配」，评审人为空时显示「未设置」；
  - 页面中没有编辑按钮；
  - 404 时显示「未找到」；
  - 有返回探索视图的入口。
  - 对应：FR-013、US3 场景 3、spec 边界情况「术语或标签已删除」。
  - 完成判定：测试失败。
- [x] T056 [US3] Q4 文案改动，先写测试（Red）：
  - `apps/web/src/__tests__/property-edit.test.tsx`：断言编辑弹窗的标签为「分级（Tier）」，属性卡片中显示「分级」；
  - `services/bff/tests/unit/test_governance.py`：断言非法 Tier 的错误消息以「分级（Tier）」开头；
  - `tests/e2e/sources.spec.ts:312`：改为 `getByLabel("分级（Tier）")`。
  - 完成判定：测试失败。

### Implementation for User Story 3

- [x] T057 [US3] 在 `services/bff/src/contexture_bff/adapters/om_assets.py` 中实现 `glossary_term_detail()` 和 `tag_detail()`；在 `services/bff/src/contexture_bff/api/catalog.py` 中增加 `GET /bff/v1/governance/glossary-terms/{fqn}` 与 `GET /bff/v1/governance/tags/{fqn}`，使用 `require_web_context`。
  - 完成判定：T053、T054 通过。
- [x] T058 [US3] 实现前端页面：
  - 新建 `apps/web/src/features/assets/GlossaryTermDetail.tsx` 与 `TagDetail.tsx`。
  - 在 `/assets/:entityType/:fqn` 路由中按类型分派：库、Schema、表进入 005 的 `CatalogAssetDetailView`，术语、标签进入新的详情页。
  - 在 `apps/web/src/features/sources/CatalogAssetDetailView.tsx` 中支持定位列。
  - 在 `ExploreView` 的页头增加「数据源管理」「添加数据源」两个入口。
  - 在 `TopBreadcrumb.tsx` 中补上子视图的面包屑（research R14）。
  - 完成判定：T051、T052、T055 通过。
- [x] T059 [US3] 实现 Q4 文案改动：
  - `apps/web/src/features/sources/PropertyEditModal.tsx:345` 的标签改为「分级（Tier）」；
  - 同文件 :346 的帮助文字中，把「业务重要程度」改为「分级（Tier）」，其余文字不变；
  - `apps/web/src/features/sources/AssetProperties.tsx:99` 改为「分级」；
  - `services/bff/src/contexture_bff/adapters/om_sources.py:804` 的消息改为「分级（Tier）须为 Tier.Tier1–Tier.Tier5」。
  - 完成判定：T056 中的单元测试通过。
- [x] T060 [US3] 新建 `tests/e2e/assets.spec.ts`，先写入「旧地址重定向」一组用例：
  - `/sources`；
  - `/sources/mock-mes`；
  - `/sources/mock-mes/assets/table/<fixture 中的 FQN>`。
  
  再在新路径下运行 T020 修改过的 005 e2e，即 `sources.spec.ts`、`sources-perf.spec.ts`、`shell-navigation.spec.ts`。
  - 对应：SC-007。
  - 完成判定：全部通过；环境阻塞时如实记录。

**Checkpoint**：三个用户故事都能独立工作，005 不退化。

---

## Phase 6: Polish & Cross-Cutting（阶段 E）

- [x] T061 [P] 编写组件测试 `apps/web/src/__tests__/assets-states.test.tsx`，覆盖：
  - **加载中**：显示加载状态，不先显示旧结果。
  - **出错**：显示真实的错误码（如 `search.index_missing`、`upstream.unavailable`）和重试入口，并且没有任何示例数据。
  - **零资产**：显示空状态，提供「添加数据源」入口，并说明可以用开发态导入。
  - **无结果**：显示无结果状态。
  - **窄屏**：视口不超过 850px 时，摘要以覆盖层显示。
  - 对应：FR-015、SC-006、spec 边界情况。
  - 完成判定：测试失败。
- [x] T062 在 `apps/web/src/features/assets/ExploreView.tsx`、`SummaryPanel.tsx` 和新建的 `apps/web/src/features/assets/assets.css` 中实现各种页面状态和窄屏样式。
  - 完成判定：T061 通过。
- [x] T063 [P] 编写单元测试 `services/bff/tests/unit/test_assets_logging.py`，覆盖：
  - assets 和 governance 详情接口每次请求输出一条 JSON 日志；
  - 日志包含 `trace_id`、`tenant_id`、操作、类型、关键词长度、条件维度、结果数、耗时；
  - 日志中不出现令牌和完整的关键词原文（只记录长度）。
  - 对应：FR-020、research R16。
  - 完成判定：测试失败。
- [x] T064 在 `services/bff/src/contexture_bff/api/assets.py` 与 `api/catalog.py` 的新路由中实现结构化日志，复用 `contexture_core.telemetry`。
  - 完成判定：T063 通过。
- [x] T065 在 `tests/e2e/assets.spec.ts` 中补充以下用例：
  - US1、US2、US3 的主路径，使用 fixture 数据；
  - SC-002：通过搜索和浏览树两条路径到达摘要和字段，操作都不超过 5 步；
  - 在 1280、768、390 三种视口下，`document.documentElement.scrollWidth ≤ clientWidth`；
  - SC-002：两条主路径同时统计总耗时，不超过 30 秒；
  - SC-003：搜索、筛选、翻页各统计至少 20 次从操作到结果出现的耗时，计算 p95 并与 2 秒比较，结果输出到 `test-results/` 并写入 acceptance 草稿；因环境故障失败的样本单独列出，不计入统计；不达标时如实记录，不放宽阈值；
  - FR-019：监听页面的网络请求，断言浏览器只请求同源的 `/bff/` 路径，不直连 OM 或 OpenSearch。
  - 完成判定：通过；p95 与 2 秒的比较结论、SC-002 的耗时都已记录。
- [x] T066 核对 SC-006：
  - 在 `apps/web/src/features/assets/`、`services/bff/src/contexture_bff/adapters/om_search.py`、`om_assets.py` 中检查是否有示例数据、写死的数值，或者出错时回退的路径；
  - 确认 T025、T061 的错误用例都已覆盖；
  - 三种情况分别写明验证方式：OM 不可用在真实环境中验证（T067）；索引缺失和零资产只由契约测试与组件测试验证，在真实环境中未验证；
  - 结论写入 acceptance 草稿。
  - 完成判定：没有发现示例数据路径，三种情况的验证方式都已写明。
- [x] T067 按 `specs/006-asset-search-summary/quickstart.md` 第 0～5 节逐项验证。OM 不可用的场景：执行 `kubectl -n contexture scale deploy/openmetadata --replicas=0`，验证完恢复为 1。
  - 完成判定：每一节都有结论。
- [x] T068 运行全部自动化验证：`make lint`、`make test`、`make coverage-check`（新增和修改代码行覆盖率不低于 80%）、`pnpm --filter @contexture/ts-api check`、`pnpm --filter @contexture/web test`、`uv run pytest -m cluster services/bff/tests/integration testdata/tests`、`make e2e`。
  - 完成判定：全部通过。因环境原因失败的项，如实记录原因与处理方式。
- [x] T069 [P] 把 T037～T039、T050 的实测结论回写到 `specs/006-asset-search-summary/research.md`（R3、R4、R6、R9），去掉已确认项的 UNCONFIRMED 标记；如果 `platform-architecture.md` 中有与之相关的描述，一并核对。
  - 完成判定：research 与代码一致。
- [x] T070 编写 `specs/006-asset-search-summary/acceptance.md`（**最后一个任务**，在 T068 之后进行）。内容包括：
  - 前置条件与数据准备：`make up`、`make seed`、`make dev-metadata`，以及 D11 的排查结论；
  - 预计用时；
  - 逐步操作与每步的预期结果，标明对应的 US1～US3 与 SC-001～SC-009；其中 SC-002 由验收人手动计时一次；
  - 开发方自动化验证的结果（T068）；
  - SC-009 中文检索观察：固定的关键词清单取自 003 表定义的中文注释，记录每个关键词的命中数和前 3 条结果，由负责人按 D10 判定；
  - 权限范围说明：宪法 IV 的 Phase 1 例外，所有登录用户看到的资产范围相同；
  - 已知限制，包括：
    - 只命中字段名时，表卡片上没有高亮；
    - 按负责人筛选时不包含列；
    - 结果窗口最多 10000 条；
    - 开发态标签会出现在「分类标签」筛选中；
    - 导入的服务在数据源管理中显示为「待配置」；
    - 无关键词浏览全部资产时，列表中包含列；
    - SC-006 中索引缺失与零资产两种情况只在契约测试和组件测试中验证；
    - OM 写索引失败会进入重试队列、用户级搜索缓存可能让新资产短暂不可见，附 T010 的实测结论；
    - research 中 UNCONFIRMED 各项的实测结论；
  - 验收记录表：日期、验收人、结果、发现的问题。
  
  所有命令都能直接复制执行。
  - 完成判定：文档完整，交给负责人。

---

## Dependencies & Execution Order

### 阶段依赖

```text
Phase 1 Setup（A）──▶ Phase 2 Foundational（B 导入 ∥ C 契约 ∥ BFF 公共 ∥ Web 公共）
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
         Phase 3 US1 (P1)   Phase 4 US2 (P1)   Phase 5 US3 (P2)
                 │                 │                 │
                 └────────┬────────┴────────┬────────┘
                          ▼                 ▼
                 Phase 6 Polish（E）──▶ T070 acceptance.md（最后）
```

- **Phase 1**：T002 依赖 T001。T001、T002 未通过时不阻塞开发，但依赖搜索的集群测试记为环境阻塞。
- **Phase 2 内部**：
  - B：T004、T005 → T006 → T007 → T008 → T009 → T010。
  - C：T011 → T012。
  - BFF 公共：T013 可以并行；T014 → T015；T016 → T017。
  - Web 公共：T018、T019、T020、T023 可以并行（Red）→ T021 → T022 → T024。T021 依赖 T012 生成的类型。
- **用户故事之间**：
  - US1 与 US2 都只依赖 Foundational，可以并行开发。
  - 两者都会改 `om_search.py`、`api/assets.py`、`ExploreView.tsx`：同时开发时先合 US1，按文件顺序执行 T030 → T044、T032 → T045、T035 → T048。
  - US3 的 T058 依赖 US1 的 ExploreView（页头入口、卡片链接），T051 依赖 US2 的 BrowseTree（在子视图中点击树）。US3 应在 US1、US2 的实现任务完成之后开始。
- **每个故事内部**：测试任务（Red）→ BFF 适配器 → 路由 → 前端组件 → 集成与实测。

### 测试先行的提交顺序（宪法 I）

每对「测试 → 实现」单独提交，测试提交在前：

| 测试 | 实现 |
| --- | --- |
| T004/T005 | T006–T008 |
| T014 | T015 |
| T016 | T017 |
| T018/T019/T023 | T021/T022/T024 |
| T025–T029 | T030–T032 |
| T033/T034 | T035 |
| T041–T043 | T044/T045 |
| T046/T047 | T048 |
| T051–T055 | T057/T058 |
| T056 | T059 |
| T061 | T062 |
| T063 | T064 |

### 可并行的任务组

- **Phase 2 Red 组**：T004、T005、T013、T014、T016、T018、T019、T020、T023
- **US1 Red 组**：T025、T026、T027、T028、T029、T033、T034
- **US1 实测组**（前置：T036 的数据就绪）：T037、T038、T039
- **US2 Red 组**：T041、T042、T043、T046、T047
- **US3 Red 组**：T051、T052、T053、T054、T055
- **Polish**：T061 与 T063 可以并行；T069 可以与 T065、T066 并行

## Parallel Example: User Story 1

```bash
# 先并行写下 US1 的全部失败测试：
Task: "T025 契约测试 services/bff/tests/contract/test_assets_search_contract.py"
Task: "T026 契约测试 services/bff/tests/contract/test_asset_summary_contract.py"
Task: "T027 单元测试 services/bff/tests/unit/test_search_criteria.py"
Task: "T028 单元测试 services/bff/tests/unit/test_search_projection.py"
Task: "T029 单元测试 services/bff/tests/unit/test_asset_summary.py"
Task: "T033 组件测试 apps/web/src/__tests__/assets-search.test.tsx"
Task: "T034 组件测试 apps/web/src/__tests__/assets-results.test.tsx"
# 提交（Red）后，T030 与 T031 可以并行实现（文件不同），然后做 T032 和 T035。
```

## Parallel Example: User Story 2

```bash
Task: "T041 契约测试 services/bff/tests/contract/test_assets_browse_contract.py"
Task: "T042 单元测试 services/bff/tests/unit/test_browse_tree.py"
Task: "T043 单元测试 services/bff/tests/unit/test_facets.py"
Task: "T046 组件测试 apps/web/src/__tests__/assets-browse.test.tsx"
Task: "T047 组件测试 apps/web/src/__tests__/assets-filters.test.tsx"
```

---

## Implementation Strategy

### MVP（Foundational + US1）

1. 完成 Phase 1（环境前置）与 Phase 2（导入工具、契约、公共基础）。
2. 完成 Phase 3 US1：搜索 → 类型列表 → 卡片 → 摘要。
3. **停下来验证**：按 quickstart 第 2 节独立验收 US1。这就是 Phase 1 计划中「006 资产业务演示」的主路径（登录 → 搜索 / 筛选 → 选择资产 → 查看摘要与字段）。

### 增量交付

1. Foundational + US1 → 演示搜索与摘要。
2. 加上 US2 → 演示浏览树、筛选、条件条、排序分页（同时满足「与 OM 一致」和发现缺失属性两项需求）。
3. 加上 US3 → 子视图统一、005 不退化、术语和标签详情、列定位。
4. Polish → 页面状态、日志、e2e、全部自动化验证 → acceptance.md → 负责人手动验收。

## Notes

- 共 70 个任务。各阶段数量：Setup 3、Foundational 21、US1 16、US2 10、US3 10、Polish 10。
- 测试中的「fixture 数据」指 `testdata/mockfactory/om_import/fixture.py` 中的声明，以及导入后 OM 中的实际实体；不引用原型数值。
- 遇到依据不足的情况，回到 research 标注为待澄清，不要自行补造。
- 不提交、不合并，除非负责人要求；不使用 squash。
