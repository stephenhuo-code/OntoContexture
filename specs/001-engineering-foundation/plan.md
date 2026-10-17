# Implementation Plan: 001 工程基座

**Branch**: `001-engineering-foundation` | **Date**: 2026-10-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-engineering-foundation/spec.md`

## Summary

按 spec 的交付清单 D1–D11，把已完成的架构设计落成一个可开工的仓库和环境：仓库骨架与公共库、`bff` 与织境 Web 的最小
版本、12 个开源组件的标准部署目录、本地一键部署、CI 门禁、离线安装包，并以“最终演示”6 步验收；
期间完成 AI 网关、Toolbox 连 Doris、系统可观测后端三项选型。架构依据见 `docs/architecture/platform-architecture.md` 与
ADR-0001–0013，技术决策见 [research.md](research.md)。

## Technical Context

**Language/Version**: Python 3.12（`bff`、公共库、工具脚本）；TypeScript 5（织境 Web）

**Primary Dependencies**:
- 后端：FastAPI、Pydantic v2 + pydantic-settings、httpx、PyJWT（JWKS 验签）、Authlib（`bff` 的 OIDC 登录）、MCP 官方 Python SDK
  （Streamable HTTP 客户端）、OpenTelemetry SDK 与 FastAPI 插桩
- 前端：React 18、Vite、TanStack Query、react-router 7（001 只做最小外壳，设计系统与 Omnigent 前端改造在 004）
- 部署：Helm、kind、CloudNativePG、Doris Operator；Keycloak realm 配置导入用 keycloak-config-cli（候选，许可在 tasks 中核实）

**Storage**: Doris（本体实例库，示例数据）；PostgreSQL（OM、Keycloak 本地、Langfuse、Airflow、`bff` 各一个 database）；OpenSearch
（OM 索引）；Fuseki（OM 的 RDF）；ClickHouse + Valkey + 对象存储（Langfuse）；PostgreSQL `bff` database（`bff` 会话，独占）

**Testing**: pytest + Testcontainers（Keycloak 等真实依赖）、Schemathesis（契约）、oasdiff（破坏性变更）、Vitest、Playwright
（最终演示的端到端测试）；组件冒烟测试为 Helm test

**Target Platform**: Kubernetes（x86_64）：001 只做本地 kind；阿里云 ACK 测试环境在 004 之后

**Project Type**: 多组件 Web 平台（1 个自建后端 + Web 前端 + 开源组件）

**Performance Goals**: 示例页面端到端 P95 ≤ 1 秒（本地）；AI 网关加 MCP Toolbox 的取数开销 P95 ≤ 100 毫秒（spike 中实测后确认）

**Constraints**: 宪法 I–VI 与部署约束；只用宽松许可组件；离线可部署；浏览器只访问 `bff`；单租户（`tenant_id` 为部署常量）

**Scale/Scope**: 本地环境建议 16 核 / 64 GB 内存（OM、OpenSearch、Doris、ClickHouse 较重，需实测）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 条款 | 检查 | 结论 |
| --- | --- | --- |
| I 测试驱动 | 公共库、`bff`、`web` 先写测试；组件配置各带冒烟测试；最终演示有端到端测试；覆盖率 ≥ 80% | 通过 |
| II 微服务与契约优先 | 只自建 `bff`；接口契约在 `contracts/` 先行，oasdiff 检测破坏性变更 | 通过 |
| III 开源与许可 | 全部组件宽松许可，开源服务清单见下文；CI 做 SBOM、许可白名单与漏洞扫描 | 通过 |
| IV 最小权限与审计 | `bff` 以客户端身份做标准令牌交换（`sub` = 人，`azp` = bff）；AI 网关记录审计；001 使用本地 Keycloak | 通过（按 Phase 1 例外不做数据层授权） |
| V 可观测性 | 公共库注入关联属性；追踪覆盖最小链路每一跳；可观测后端在 D10 选定 | 通过 |
| VI 以服务方式集成 | 组件均以独立服务部署；OM 从织境维护的仓库构建（001 用上游 2.0.3 标签，不含补丁）；CI 核对 OM 与 Omnigent 发布分支相对上游标签的差异与 `PATCHES.md` 一一对应 | 通过 |
| 部署约束 | 伞形 Chart 可直接用于后续的测试环境；离线安装包；单租户（v1.5.0 例外） | 通过（按例外） |
| 开发流程与质量门禁 | CI 门禁、本地部署、离线打包即交付物 D6、D8、D9；测试环境部署在 004 之后 | 通过 |

## 实施方案（按交付物）

| # | 交付物 | 做法 | 依赖 |
| --- | --- | --- | --- |
| D1 | 仓库骨架 | 按 ADR-0009 建目录；`pyproject.toml`（uv workspace：py-core、bff、tools）、`pnpm-workspace.yaml`（web、ts-api）；`Makefile` 目标：`test`、`up`、`down`、`seed`、`e2e`、`components-check`、`offline-package`；pre-commit（ruff、pyright、eslint） | — |
| D2 | 公共库 v0.1 | `auth`：PyJWT 加 JWKS 缓存验签，解析 `sub`、`azp`、角色，`tenant_id` 取自 `config`；FastAPI 依赖项统一返回 401 / 403<br>`mcp`：调用 Keycloak 令牌端点做标准令牌交换（受众 = AI 网关），按受众缓存；用 MCP SDK 的 Streamable HTTP 客户端调用工具，并传递 `traceparent`<br>`telemetry`：OTel 初始化，按 `contracts/otel/attributes.md` 注入关联属性<br>`ontology`：读取 OM 中已审批的术语与属性，缓存<br>`errors`：按 `contracts/schemas/error.json` 输出<br>`config`：pydantic-settings | D1 |
| D3 | `bff` 最小版本 | FastAPI，分层只有 `api` 与 `adapters`，另有 `migrations/`（Alembic，会话表）（ADR-0009）。按 BFF 模式由 `bff` 完成 OIDC 登录：`/bff/v1/auth/login`、`/callback`、`/logout`，会话存 PostgreSQL 的独占 database `bff`（不新增组件），浏览器不持有令牌；业务接口 `GET /bff/v1/me`、`GET /bff/v1/object-types/{typeKey}/objects`（契约 `contracts/openapi/skeleton.yaml`）；后者经 `ontology` 读 OM，经 `mcp` 调 Toolbox 工具 `list_objects` | D2、D10①② |
| D4 | 织境 Web 最小外壳 | React 单页应用：登录跳转、示例页面（对象定义表 + 设备列表）；前端 API 客户端由契约生成到 `packages/ts-api/`；构建为 nginx 静态镜像 | D3 |
| D5 | 组件部署目录 | 每个组件：`component.yaml`（版本、镜像来源、许可、定制级别、负责人）、Chart 或上游 Chart 引用、`values/base.yaml` 与各环境参数、`config/`、`tests/`。组件与来源见下表 | D1 |
| D6 | 本地一键部署 | 伞形 Chart `deploy/helm/contexture/` 汇总全部组件与 `bff`、`web`；kind 配置与本地 Keycloak（26.8.0，导入织境 realm）；`make up` 部署并等待就绪；`make seed` 预置 OM 对象定义与 Doris 示例数据 | D5 |
| D8 | CI 门禁 | GitHub Actions：构建；补丁一致性检查（`tools/patches_check.py`：OM 与 Omnigent 发布分支相对上游标签的每个提交都须在 `PATCHES.md` 登记，否则失败）；单元 / 契约 / 集成测试与覆盖率 ≥ 80%；ruff、pyright、eslint；oasdiff；Syft 生成 SBOM，Grype / Trivy 漏洞扫描，许可白名单检查；`components-check`（脚本放 `tools/`）；测试环境的自动部署在 004 之后加入 | D1、D5 |
| D9 | 离线安装包 | 从各组件 `component.yaml` 汇总镜像清单，导出镜像与 Chart；提供安装脚本；在断网 kind 中验证安装 | D6 |
| D10 | 三项选型 | ① AI 网关：agentgateway 与 Agent Router 各搭一套，按 ADR-0013 的 4 项（Toolbox 连 Doris、审计字段、模型网关、令牌受众）对比后选定；② Toolbox 的 mysql 数据源连 Doris 执行 `list_objects`，不行则改用 Doris MCP Server；③ 可观测后端：候选 Prometheus + Jaeger + OpenSearch Dashboards，部署后能查服务指标、日志与追踪 | D5（基础组件就绪） |
| D11 | 实际用时记录 | 每个交付物完成时记录用时，001 结束时汇总，更新开发计划第 3 节的估算 | 全部 |

**组件与来源（D5）**

| 组件 | 来源 | 本地 | 测试环境 |
| --- | --- | --- | --- |
| Keycloak | 官方镜像 | 部署 26.8.0，导入织境 realm | 004 之后接入现有实例（只导入织境的客户端与角色） |
| OpenMetadata | 从 `third_party/openmetadata/` 构建（上游 2.0.3 标签），开启 RDF | 部署 | 部署 |
| Jena Fuseki、OpenSearch | 官方镜像 / Chart | 部署 | 部署 |
| PostgreSQL | CloudNativePG | 部署 | 部署 |
| Doris | Doris Operator | 部署 | 部署 |
| AI 网关 | D10 选定者的官方 Chart | 部署 | 部署 |
| MCP Toolbox | 官方镜像，织境自写 Chart | 部署 | 部署 |
| OTel Collector | 官方 Chart | 部署 | 部署 |
| Langfuse（含 ClickHouse、Valkey、对象存储） | 官方 Chart；对象存储本地用 SeaweedFS、测试环境用 OSS | 部署 | 部署 |
| Airflow | 官方 Chart，KubernetesExecutor | 部署（001 只验证就绪） | 部署 |
| nginx（`web`） | 织境构建的静态镜像 | 部署 | 部署 |
| 可观测后端 | D10 选定 | 部署 | 部署 |

## 开源服务清单（宪法 III）

版本为初定版本（2026-10-17 查得的最新稳定版），在 D5 中锁定到各组件的 `component.yaml`，并与 OpenMetadata 2.0.3 的兼容要求核对
（OpenSearch、PostgreSQL、Fuseki 以 OM 支持的版本为准）。

| 组件 | 初定版本 | 许可 | 用途 | 所在位置 | 可替换方案 |
| --- | --- | --- | --- | --- | --- |
| OpenMetadata | 2.0.3（自建镜像 `2.0.3-ctx.0`） | 服务端 Apache-2.0；采集框架与内置 MCP 为 CCL 1.0（已批准例外）；界面 CCL 1.0（不交付） | 本体、元数据、血缘、审批、上下文 | 组件 `openmetadata` | DataHub（Apache-2.0） |
| Keycloak | 26.8.0（与现有 Keycloak 一致） | Apache-2.0 | 身份、角色、标准令牌交换 | 组件 `keycloak` | Zitadel（Apache-2.0）、Authentik |
| Jena Fuseki | 6.x（按 OM 要求锁定） | Apache-2.0 | OM 的 RDF 存储 | 组件 `fuseki` | 不启用 OM 的 RDF |
| OpenSearch | 3.9.0（按 OM 兼容矩阵锁定） | Apache-2.0 | OM 搜索索引；服务日志 | 组件 `opensearch` | Elasticsearch（许可不宽松，不选） |
| PostgreSQL + CloudNativePG | PostgreSQL 17；CloudNativePG 1.30.1 | PostgreSQL License；Apache-2.0 | OM、Keycloak、Langfuse、Airflow 的数据库；`bff` 会话（独立 database） | 组件 `postgresql` | MySQL（OM 支持） |
| Apache Doris + Doris Operator | 4.1.5；Operator 26.0.1 | Apache-2.0 | 本体实例库 | 组件 `doris` | StarRocks（Apache-2.0） |
| AI 网关（D10 选定其一） | agentgateway 1.6.0 / Agent Router 1.2.0 | Apache-2.0 | MCP 网关 + 模型网关、审计 | 组件 `ai-gateway` | 自建薄网关（ADR-0013 后备） |
| MCP Toolbox | 1.14.0 | Apache-2.0 | 数据库 MCP 服务（只读查询工具） | 组件 `mcp-toolbox` | Apache Doris MCP Server（Apache-2.0） |
| OpenTelemetry Collector | 0.163.1 | Apache-2.0 | 追踪汇聚与转发 | 组件 `otel-collector` | 各组件直连后端 |
| Langfuse | 4.63.0 | MIT（不启用 `ee` 目录功能） | 决策轨迹 | 组件 `langfuse` | Arize Phoenix（Elastic License，不选）、自建 |
| ClickHouse | 26.9（Langfuse 依赖） | Apache-2.0 | Langfuse 存储 | 组件 `langfuse` | — |
| SeaweedFS | 4.48 | Apache-2.0 | 对象存储（本地 / 离线） | 组件 `langfuse` | 阿里云 OSS（测试环境） |
| Valkey | 9.1.2 | BSD-3-Clause | Langfuse 缓存 | 组件 `langfuse` | — |
| Apache Airflow | 3.3.2 | Apache-2.0 | 管线编排（001 只验证就绪） | 组件 `airflow` | Argo Workflows（Apache-2.0） |
| Envoy Gateway | 1.9.2 | Apache-2.0 | 边缘网关与路由 | 组件 `envoy-gateway` | ingress-nginx（已退役，不选） |
| nginx | 1.31.7 | BSD-2-Clause | `web` 静态资源服务 | 组件 `web` | Caddy（Apache-2.0） |
| 可观测后端（D10 候选） | Prometheus 3.15.0；Jaeger 2.22.0；OpenSearch Dashboards 3.9.0 | Apache-2.0 | 服务指标、追踪、日志查看 | 组件 `prometheus`、`jaeger`、`opensearch-dashboards` | Grafana 系（AGPL，不选） |

## 实施顺序

按 AI 辅助估算约 2 周（开发计划 001），建议 2–3 人并行：

| 周 | 内容 |
| --- | --- |
| 第 1 周 | D1 仓库骨架 → D8 基础 CI；D2 公共库；D5 先落地 Keycloak、PostgreSQL、OM、Doris、MCP Toolbox；D10 ①②（AI 网关与 Toolbox 连 Doris，D3 依赖其结论） |
| 第 2 周 | D3 `bff`、D4 `web`；D5 其余组件；D6 伞形 Chart 与 `make up`；D8 补齐扫描；D9 离线包；D10 ③；最终演示（本地）；D11 汇总用时 |

关键路径：D1 → D2 → D10①② → D3 → D4 → 最终演示。

## Project Structure

### Documentation (this feature)

```text
specs/001-engineering-foundation/
├── spec.md              # 交付清单与最终演示
├── plan.md              # 本文件
├── research.md          # 技术决策
├── data-model.md        # 请求上下文、审计、示例对象
├── quickstart.md        # 验收指南（对应最终演示）
├── contracts/
│   ├── openapi/skeleton.yaml
│   ├── schemas/error.json
│   ├── schemas/audit-event.json
│   └── otel/attributes.md
└── tasks.md             # /speckit-tasks 产出
```

### Source Code (repository root)

本特性创建的目录（完整布局见 ADR-0009）：

```text
apps/web/                         # D4 最小外壳
services/bff/                     # D3
packages/py-core/                 # D2 contexture-core：auth、mcp、telemetry、ontology、errors、config
packages/ts-api/                  # 由契约生成的前端客户端
contracts/{openapi,mcp,schemas,otel}/   # 由本特性 contracts/ 落位；mcp/ 放示例工具 list_objects 的契约
deploy/components/<组件>/          # D5
deploy/helm/contexture/           # D6 伞形 Chart
deploy/kind/                      # D6 本地集群配置
deploy/offline/                   # D9
.github/workflows/                # D8
tools/                            # components-check、离线打包、种子数据等脚本
third_party/openmetadata/         # src/ 为子仓库（stephenhuo-code/OpenMetadata，ctx/2.0.3）；UPSTREAM.yaml、PATCHES.md、build/（ADR-0011）
tests/e2e/                        # 最终演示的端到端测试
```

**Structure Decision**：采用 ADR-0009 的 monorepo 结构；最小链路使用真实组件，后续特性在其上扩展，不丢弃重写。

## Complexity Tracking

无违反宪法的设计，不适用。

## Post-Design Constitution Re-check

交付物与组件逐项对照宪法：只自建 `bff`（II）；契约先行（II）；组件许可与扫描（III）；令牌交换、审计、只读取数（IV）；
最小链路全程追踪（V）；组件以服务方式集成、OM 从镜像仓库构建（VI）；单租户与离线包（部署约束）。结论：通过。

## 需要用户提供或确认

1. 织境维护的 OM 仓库：已就绪（`stephenhuo-code/OpenMetadata`，分支 `ctx/2.0.3`，子仓库 `third_party/openmetadata/src/`）。
2. 本地开发机配置是否满足 16 核 / 64 GB；不满足时 D6 提供精简配置（降低副本与资源）。
3. 模型服务 key 由负责人在验证 AI 网关时自行配置（D10①）。
4. 阿里云测试环境与接入现有 Keycloak 放到 004 之后（见开发计划 004）。
5. **004 开工前决定**：Omnigent 前端复制到 `apps/web/` 后深度改造，与宪法 VI“不得在两种方式之外维护分叉”冲突（analyze C3）。
   需修订宪法增加衍生代码例外，或改为补丁方式。
