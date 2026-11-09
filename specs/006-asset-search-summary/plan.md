# Implementation Plan: 资产搜索与摘要（Asset Search & Summary）

**Branch**: `006-asset-search-summary` | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)

**Input**:
- 规格：`specs/006-asset-search-summary/spec.md`，含 2026-11-09 的 clarify 与 plan 前澄清（Q3 = A，Q4 = A）
- 原型：`prototype/index.html`
- 调研：[页面结构方案](prototype/page-structure.md)、[OM 搜索能力对齐调研](prototype/openmetadata-alignment.md)

## Summary

织境把浏览、搜索、快速筛选、条件条、排序分页、结果卡片和只读摘要合并到一个「数据资产」页面（`/assets`），交互与 OpenMetadata 2.0.3 的 Explore 一致。005 的数据源管理和资产详情成为该页面的子视图；旧的 `/sources/*` 地址重定向到新地址。

技术路线：

1. **搜索全部使用 OM 服务端**（research R1–R8）：
   - BFF 新增 8 个只读接口，把结构化条件 `SearchCriteria` 翻译成 OM 的请求参数：
     - 主列表调用 `/v1/search/query`；
     - 类型计数调用 `/v1/search/entityTypeCounts`；
     - 筛选项与浏览树调用 `/v1/search/aggregate`；
     - 摘要与详情调用实体的 `/name/{fqn}` 接口。
   - BFF 生成并校验 `query_filter`，总是带上 `deleted=false`；不合法的条件返回明确错误。
   - 不自建索引，不打分；相关性使用 OM 默认的 searchSettings。
2. **BFF 只做转换**：
   - 复用 005 的 `OmClient`（用户委托令牌、错误映射、追踪），以及 `governance_view` 中拆分 Tier 和标签的逻辑；
   - 不新增服务、表或持久化状态。
3. **Web**：
   - 新增 `features/assets/`，包括探索视图、浏览树（由 005 的 `CatalogTree` 改造）、快速筛选、条件条、卡片、摘要、术语详情和标签详情；
   - 005 的 `SourcesWorkspace` 和资产详情迁到 `/assets` 下；
   - 搜索条件保存在布局层的内存中，会话内保留，不写入地址。
4. **开发态导入**：在 `testdata/mockfactory` 中新增 `om-import` 子命令，按 003 的表定义经 OM `PUT` 幂等写入。导入的资产用专用分类标签标识为开发态测试元数据，服务不带连接（research R12、R13）。
5. **环境前置**：先排查 OpenSearch 反复重启的问题（D11、research R15）。中文分词沿用 EN 映射，验收时实测（D10）。

## Technical Context

**Language/Version**：
- Python 3.12：`services/bff`、`packages/py-core`、`testdata/`
- TypeScript 5.7 / React 18.3.1 / React Router 7.18.2 / Vite 8.3.4：`apps/web`、`packages/ts-api`

**Primary Dependencies**：
- 后端：FastAPI、Pydantic v2、httpx（BFF，沿用）
- 前端：@tanstack/react-query 5.101.2；`@contexture/ui`（基于 radix-ui 1.6.3）
- 契约与类型：openapi-typescript 7.13.0 / openapi-fetch 0.17.0
- 平台组件：OpenMetadata Server 2.0.3（`2.0.3-ctx.0`）、OpenSearch 3.4.0、Keycloak（令牌交换）

**不新增任何运行时依赖。**

**Storage**：
- 正本在 OpenMetadata，包括 PostgreSQL 与 OpenSearch 索引。
- BFF 仍只有 002 的 `bff_sessions`，**不新增表**。
- 搜索条件只保存在浏览器内存中。

**Testing**：
- Python：pytest，包括单元测试、Schemathesis / jsonschema 契约测试（`services/bff/tests/contract`），以及在真实 kind 集群上运行的 `-m cluster` 集成测试（真实 OM / OpenSearch）。
- 前端：vitest 加 Testing Library。
- 端到端：Playwright，覆盖 1280 / 768 / 390 三种视口。
- 断言依据导入工具的 fixture 和 OM 实际数据，不使用原型数值。

**Target Platform**：Kubernetes（本地 kind；阿里云 ACK），现有 Chart。

**Project Type**：Web 应用（`apps/web` + `services/bff`）加测试设施（`testdata/`）。

**Performance Goals**：本地验收环境中，95% 的搜索、筛选、翻页在 2 秒内出结果（SC-003）。输入建议防抖 400ms。

**Constraints**：
- 浏览器只调用 BFF，BFF 只调用 OM 的公开 REST 接口；
- OM 结果窗口最多 10000 条，查询超时 30 秒；
- 只读，Phase 1 不做数据层授权；
- 新增和修改代码的行覆盖率不低于 80%。

**Scale/Scope**：
- 资产以数据库类和治理类为主。导入工具从 003 的 MES、QMS、数仓定义生成数据，005 的实际采集结果可以同时使用。
- 共 3 个用户故事、20 条功能需求、9 条成功标准。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*（宪法 v2.2.0）

| 条款 | 结论 | 依据 |
| --- | --- | --- |
| I 测试驱动 | PASS | 顺序为：先合入契约、写契约测试（Red），再实现。BFF 的条件翻译和投影用单元测试覆盖。集成测试使用真实 OM / OpenSearch（`-m cluster`），不用 mock 代替被集成的系统。前端组件测试在 e2e 之前完成。保留测试先行的提交顺序，不使用 squash。新增和修改代码的行覆盖率不低于 80%（`make coverage-check`） |
| II 微服务与契约优先 | PASS | 不新增服务，能力放在现有 BFF 的边界内（浏览器会话 API 与外部服务适配）。先改 `contracts/openapi/bff.yaml`（版本 0.2.0 → 0.3.0，只增不改，向后兼容），再写契约测试，再生成 `packages/ts-api`。只调用 OM 公开 REST，不读写 OM 的数据库或 OpenSearch |
| III 开源优先与许可 | PASS | 搜索、聚合、计数、相关性全部复用 OM 服务端（Apache-2.0）。不复制 OM UI 代码（CCL 1.0），只阅读源码来理解交互，并在 research 中注明出处；浏览树大类清单和字段映射作为数据重新编写。不新增依赖。组件清单见下表 |
| IV 最小权限与审计 | PASS（Phase 1 例外） | 新路由全部经过 `require_web_context`（admin / ai-engineer），以 RFC 8693 用户委托令牌调用 OM。OM 的 `enableAccessControl=false`，`/aggregate` 也不过滤，所以结果范围对所有登录用户相同；这符合 Phase 1 例外（只做到角色一级，数据层授权推迟到二期），写入 acceptance.md。导入工具使用 provisioner 服务身份，凭证只来自环境变量，不进仓库，也不打印 |
| V 可观测性 | PASS | 复用 `contexture_core.telemetry`：`bind_context`、JSON 日志（含 trace_id、tenant_id），对 OM 的调用使用 `traced_client`。每次搜索、摘要、详情请求输出一条结构化日志（research R16） |
| VI 以服务集成、定制分级 | PASS | 只用配置和公开接口。不修改 OM searchSettings，不修改索引映射，不安装插件，不打补丁。D11 的排查如需调整，只改 OpenSearch 的 Helm values（第一级「配置」） |
| VII 数据模型复用 | PASS | 不新增实体或表。资产、列、术语、标签、Tier、数据级别、认证全部使用 OM 原生实体与索引字段。开发态标识使用 OM 原生的分类和标签，复用结论见 research R12。DTO 与 OM 字段的映射见 data-model.md |
| 部署约束（Phase 1 单租户） | PASS | 不涉及多租户；日志保留 `tenant_id`（部署常量） |
| 开发流程：原型先行 | PASS | 原型已同步：「分级（Tier）」文案、去掉地址状态、列定位示意，以及术语和标签详情。详情页字段清单由负责人于 2026-11-09 确认采用 research R9 的 OM 原生字段清单，原型已按此更新；负责人同日同意按 analyze 建议修订，spec「原型同步」已标为完成（FR-013） |
| 开发流程：原型与真实数据边界 | PASS | 所有数字、名称、时间都来自 OM。BFF 和前端都没有示例数据，出错时不回退。测试只断言 fixture 和 OM 实际数据。做不到的部分写进 acceptance.md：中文检索效果、字段名命中时不高亮、负责人筛选不包含列、10000 条结果窗口 |
| 开发流程：acceptance.md | PASS | tasks 的最后阶段编写 acceptance.md，内容包括环境前置（D11）、SC-009 的观察记录、权限范围说明，以及上述已知限制 |

**Post-design re-check（Phase 1 后）**：契约只新增接口与 schema，没有修改已有接口。数据模型没有新增持久化内容；quickstart 没有引入示例数据路径。全部 PASS，结论不变。

### 开源服务与组件清单（宪法 III）

| 组件 | 版本 | 许可 | 用途 | 部署单元 | 可替换方案 |
| --- | --- | --- | --- | --- | --- |
| OpenMetadata Server | 2.0.3（`2.0.3-ctx.0`） | Apache-2.0 | 搜索、聚合、类型计数、实体读取；资产与治理正本 | `openmetadata` | DataHub、Apache Atlas |
| OpenSearch | 3.4.0 | Apache-2.0 | OM 的搜索索引（只经 OM 访问） | `opensearch` | Elasticsearch（许可需另行评审） |
| Keycloak | 平台锁定版本 | Apache-2.0 | 用户身份与令牌交换 | `keycloak` | 其他 OIDC IdP |
| FastAPI / Pydantic / httpx | `uv.lock` 锁定 | MIT / BSD | BFF | `services/bff` | — |
| React / React Router / Vite / react-query | 18.3.1 / 7.18.2 / 8.3.4 / 5.101.2 | MIT | Web | `apps/web` | — |
| openapi-typescript / openapi-fetch | 7.13.0 / 0.17.0 | MIT | 由契约生成前端类型与客户端 | `packages/ts-api` | — |

本特性不新增组件。清单与 `docs/architecture/platform-architecture.md` 第 4 节一致。

## Project Structure

### Documentation (this feature)

```text
specs/006-asset-search-summary/
├── prototype/             # 原型与调研（页面结构、OM 对齐、架构图）
├── spec.md                # 规格（含 clarify 与 plan 前澄清）
├── plan.md                # 本文件
├── research.md            # Phase 0：R1–R16 技术决策与源码出处
├── data-model.md          # Phase 1：OM 原生实体映射、SearchCriteria、投影与白名单
├── quickstart.md          # Phase 1：验证场景
├── contracts/openapi.yaml # Phase 1：BFF 增量契约（实施时合入 contracts/openapi/bff.yaml）
├── tasks.md               # Phase 2（$speckit-tasks 生成）
└── acceptance.md          # 实施收尾
```

### Source Code (repository root)

```text
contracts/openapi/bff.yaml                       # 合入 006 增量；版本升为 0.3.0；登记新的错误码
packages/ts-api/src/bff.d.ts、index.ts           # 重新生成；index.ts 导出新类型

services/bff/src/contexture_bff/
├── adapters/om_search.py        # 新增：SearchCriteria → OM 参数（index / q 转义 / query_filter / 排序 / 分页校验）；
│                                #   结果投影（高亮片段、命中字段、来源标识）；浏览树与筛选项聚合；建议；错误识别
├── adapters/om_assets.py        # 新增：摘要、术语详情、标签详情的实体读取；列 → 所属表
├── adapters/om_sources.py       # 修改：Tier 错误文案改为「分级」（Q4）；抽出 tags 拆分函数供新模块复用
├── api/assets.py                # 新增：/bff/v1/assets/*（search、type-counts、facets、browse、suggestions、summary）
├── api/catalog.py               # 修改：/bff/v1/governance/glossary-terms/{fqn}、/governance/tags/{fqn}
└── main.py                      # 挂载 assets 路由；Services 中注入搜索 / 摘要适配器（共用同一个 OmClient）
services/bff/tests/
├── unit/test_search_criteria.py、test_search_projection.py、test_browse_tree.py、test_asset_summary.py
├── contract/test_assets_search_contract.py、test_asset_summary_contract.py、test_assets_browse_contract.py、test_governance_detail_contract.py
├── integration/test_assets_search_cluster.py、test_assets_summary_cluster.py
└── om_fake.py                   # 扩展：/search/query、/entityTypeCounts、/aggregate、术语和标签读取的内存假实现（只用于单元和契约测试）

apps/web/src/
├── App.tsx                      # /assets、/assets/sources/*、/assets/:entityType/:fqn；/sources/* 重定向
├── layout/navigation.ts、SecondaryNav.tsx、AppShell.tsx、PageHeader.tsx   # 一级「资产」指向 /assets；去掉两个二级链接；二级栏放浏览树或类型列表
├── i18n/zh-CN.ts                # 006 新增文案；「分级（Tier）」
├── features/assets/             # 新增：AssetsLayout（条件上下文）、ExploreView、TopBreadcrumb（顶栏面包屑）、BrowseTree、TypeList、SearchBar（范围与建议）、
│                                #   QuickFilters、FilterChips、ResultCard、SummaryPanel、GlossaryTermDetail、TagDetail、api.ts、queries.ts
└── features/sources/            # 修改：SourcesWorkspace 路由基准改为 /assets/sources；format.ts 的 assetHref；
                                 #   CatalogAssetDetailView 支持定位列；PropertyEditModal、AssetProperties 改用「分级（Tier）」；
                                 #   CatalogTree 由 features/assets/BrowseTree 取代后删除
apps/web/src/__tests__/          # 新增 assets-*.test.tsx；修改 navigation、shell-pages、catalog、sources-* 等受影响的测试
tests/e2e/assets.spec.ts         # 新增；修改 sources.spec.ts、shell-navigation.spec.ts、sources-perf.spec.ts

testdata/mockfactory/
├── om_import/                   # 新增：fixture 定义（由 schema/{mes,qms,dw}.py 生成）、PUT 写入、统计、撤除、目标环境检查
└── __main__.py                  # 新增 om-import 子命令（--target local 必填；--remove）
testdata/tests/                  # 单元测试（fixture 生成、拒绝写入）与 -m cluster 集成测试（幂等、只管理自有资产）
Makefile                         # dev-metadata、dev-metadata-remove
deploy/components/opensearch/values/   # 只在 D11 排查确认需要时调整（配置级别）
```

**Structure Decision**：沿用现有 monorepo，不新增服务或包。

- 搜索适配器放在 BFF 的 `adapters/` 下，与 `om_client.py`、`om_sources.py` 并列。py-core 没有通用的 OM 委托令牌客户端（`ontology.py` 使用的是 bot 令牌），把它抽到 py-core 不在本特性范围内。
- 前端新建 `features/assets/` 存放探索相关组件；005 的组件留在 `features/sources/`，只调整路由和链接。
- 导入工具放在 `testdata/`（FR-017），与 003 的 `mockfactory` 在同一个包中，复用其表定义。

## 契约与先行测试

1. **合入契约**：把 `contracts/openapi.yaml` 合入 `contracts/openapi/bff.yaml`，并在 `info.description` 中登记 4 个新错误码。然后运行 `pnpm --filter @contexture/ts-api generate`，再运行 `check`。
2. **先写的契约测试**（Red，`services/bff/tests/contract/`，使用 `contract_helpers.check` 和 `om_fake`）：
   - `searchAssets`：
     - 200 的响应符合 `SearchPage` schema；
     - 维度不在白名单、仅表类型可用的维度用在非表类型下、`pageSize=20`、超过结果窗口、`scope` 与 `entityType` 不一致，都返回 422，且错误体符合 `error.json`；
     - OM 返回 500 `Failed to find index` 时 → 503 `search.index_missing`；
     - OM 返回 `timed_out=true` 时 → 504；
     - OM 不可达时 → 502。
   - `countAssetTypes`：结果中没有计数为 0 的项；`defaultType` 的规则（FR-007）。
   - `getAssetFacet`：`supportsNone` 只在 5 个维度上为 true；结果中不出现「无」选项。
   - `browseAssets`：根节点中没有计数为 0 的项；`parentPath` 中有跳层时返回 422。
   - `suggestAssets`：每组不超过 5 条；列项带有 `parentTable`。
   - `getAssetSummary`：分别覆盖 table、tableColumn、glossaryTerm、未知 FQN（404）。
   - `getGlossaryTermDetail`、`getTagDetail`：200 和 404；响应中没有可编辑字段。
   - 已有的 `test_contract.py`（Schemathesis）自动覆盖新路径。
3. **单元测试**（Red）：
   - 关键词转义，以及大写 AND / OR / NOT 的处理；
   - `query_filter` 的结构：同维度内为「或」、跨维度为「且」、「无」用 `must_not exists`、`deleted=false`；
   - 筛选项计数时排除本维度；
   - 浏览树每层的字段与过滤条件；
   - 高亮片段的解析，以及防止 HTML 注入；
   - 命中字段的统计规则；
   - tags 的拆分（Tier、数据级别、术语、开发态标识）；
   - 列 → 所属表。

## 005 受影响范围（SC-007）

| 类别 | 项 | 改动 |
| --- | --- | --- |
| 路由 | `/sources`、`/sources/:name`、`/sources/:name/assets/:entityType/:fqn`、向导 | 迁到 `/assets/sources/*` 与 `/assets/:entityType/:fqn`；旧地址重定向（research R14） |
| 组件 | `App.tsx:39-42`、`navigation.ts:32-79,96-98`、`SecondaryNav.tsx:22-27,71`、`AppShell.tsx:22`、`SourcesWorkspace.tsx:23-77`（抽屉与 `navigate`）、`CatalogTree.tsx`、`format.ts:180-187`（`assetHref`）、`CatalogAssetDetailView.tsx`、`SourceCatalog.tsx:64`、`NotOpenPage` 的使用处 | 按新路由修改；浏览树替换 `CatalogTree` |
| Tier 文案（Q4） | `PropertyEditModal.tsx:345-346`、`AssetProperties.tsx:99`、`om_sources.py:804`、`tests/e2e/sources.spec.ts:312` | 「重要程度（Tier）」改为「分级（Tier）」，「业务重要程度」相应调整 |
| Web 单元测试 | `navigation.test.tsx:70-71,137-157,186`、`shell-pages.test.tsx:32`、`catalog.test.tsx`（`/sources/*` 路由与树名「数据源目录」）、`source-wizard`、`source-tasks`、`sources-list`、`property-edit`、`session.test.tsx:192`、`login-page.test.tsx:42-46`、`api.test.ts:50` | 先改断言（Red），再改实现 |
| e2e | `sources.spec.ts`（资产地址 :319,331,552；树 :103,242；抽屉 :573；Tier :307-315）、`sources-perf.spec.ts:75`、`shell-navigation.spec.ts:28-42,114-115,149` | 改用新路径；新增旧地址重定向用例 |

## 成功标准 → 验证手段

| SC | 验证 |
| --- | --- |
| SC-001 可搜到、可浏览 | 集成测试：导入后，fixture 中每张表按英文名都能搜到，并在浏览树对应节点下找到；浏览树、类型列表、筛选项的计数与直接调用 OM 的结果相同；另有 e2e 抽查 |
| SC-002 主路径效率 | e2e：通过搜索和浏览树两条路径到达摘要和字段，操作步数不超过 5；手动验收计时 |
| SC-003 响应速度 | e2e 计时，统计 p95，写入 acceptance.md；环境故障单独记录 |
| SC-004 组合条件正确 | 集成测试：关键词、位置、同维度多选、跨维度组合、「无」各一组用例，与直接调用 OM 的同条件结果比较，总数和 ID 集合一致 |
| SC-005 同名可辨 | 集成测试与 e2e：同名表的卡片和摘要面包屑包含服务和 Schema |
| SC-006 不造数据 | 契约测试：模拟 OM 500、index missing、超时；e2e：缩容 OM 后显示真实错误；代码审查确认没有示例数据路径 |
| SC-007 005 不退化 | 已有的 005 Web 单元测试和 e2e 在新路径下全部通过；新增旧地址重定向的 e2e；手动按 005 acceptance 重走 |
| SC-008 导入幂等 | `-m cluster` 测试：连续运行两次，第二次新建数为 0，测试资产总数不变，005 服务的 version 和 updatedAt 不变；不带 `--target` 时拒绝写入 |
| SC-009 中文检索观察 | 手动验收，使用固定的关键词清单，结果记入 acceptance.md，由负责人按 D10 判定 |

## 实施阶段与闸门

| 阶段 | 内容 | 完成标志（闸门） |
| --- | --- | --- |
| A 环境前置 | 排查 OpenSearch 反复重启（D11）；确认 `-m cluster` 能稳定访问 OM 搜索 | 观察 10 分钟内重启次数不增长；排查结论写入 acceptance 草稿。未解决时继续开发，但搜索相关的集群测试按「环境阻塞」记录 |
| B 测试数据 | `mockfactory om-import`：fixture、幂等、只管理自有资产、撤除、目标环境检查（先写测试） | `-m cluster` 测试通过：导入两次，第二次新建数为 0；导入后能搜到 |
| C 契约与 BFF | 合入契约 → 生成 ts-api → 写契约和单元测试（Red）→ `om_search.py`、`om_assets.py`、路由（Green）→ 集成测试 | 契约、单元、集成测试全部通过；SC-001、SC-004 的集成用例通过；代码中没有示例数据路径 |
| D Web | 路由与导航迁移，005 受影响的测试先改断言 → 探索视图 → 浏览树 → 筛选与条件条 → 卡片与摘要 → 术语和标签详情（research R9 已确认的字段清单）→ 列定位 → Tier 文案 | 组件测试通过；三种视口没有横向溢出；005 的单元测试和 e2e 在新路径下通过 |
| E 验收 | `make lint`、`make test`（覆盖率）、`make coverage-check`、`make e2e`；编写 acceptance.md（含 SC-003 计时、SC-009 观察、已知限制） | 负责人手动验收 |

## 负责人决定记录

- 2026-11-09：术语和标签详情的字段清单采用 research R9 的 OM 原生字段清单（FR-013）；spec Clarifications 与原型已同步。当前没有待确认项。

## Complexity Tracking

没有违反宪法的项。

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| 无 | — | — |
