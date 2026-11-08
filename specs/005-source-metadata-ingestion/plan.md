# Implementation Plan: 源系统元数据采集（Source Metadata Ingestion）

**Branch**: `005-source-metadata-ingestion` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-source-metadata-ingestion/spec.md`（含 2026-11-07 澄清）与原型 `prototype/index.html`

**背景**：首轮实现（BFF 用 bot 令牌取明文密码、在 BFF 进程内连库采集、伪造运行状态、前端失败回退示例数据）已整体废弃，
本计划从保存点 1 重新设计。负责人原则：OpenMetadata 是什么样就尽量一致，第一期不加功能。

## Summary

织境提供数据源接入与元数据目录的操作界面；**数据源、采集任务、运行状态、元数据与血缘全部以 OpenMetadata 2.0.3 为正本，
采集由 OM 部署到平台独立的 Airflow 3.3.2 执行**，BFF 只调用 OM 公开 API，且以登录用户的委托令牌调用（OM 对非 bot 身份自动脱敏密码）。

技术路线：

1. **基础设施先行（阶段 A，后续阶段的闸门）**：Airflow 改用从 OM 子仓库构建的采集镜像（含 managed-apis 与五类连接器）；
   OM 打开 `AirflowRESTClient` 指向 Airflow；DAG 与生成配置共享存储；Keycloak 增加 OM 受众与角色声明，OM 用 `jwtTeamClaimMapping`
   入组。用真实数据源走通“测试连接 → 部署 → 触发 → 状态与日志回写”后才进入应用开发。
2. **测试数据**：003 MES / QMS 补只读元数据账号；mock-mes / mock-qms 实例内新建 `viewlab` 视图测试库（含受限账号）。
3. **BFF**：新增 `/bff/v1/sources*`、`/bff/v1/catalog/*`、`/bff/v1/governance/options`（契约见 contracts/openapi.yaml），
   适配 OM 接口（research R7），不连源库、不写运行状态、不内置示例数据。
4. **Web**：按原型的页面结构、交互与状态实现 `/sources`、四步向导、详情四页签、两类任务与运行、目录与属性编辑；
   所有数字、时间、运行与表结构来自 BFF，无数据显示空状态，出错显示真实错误。

## Technical Context

**Language/Version**: Python 3.12（`services/bff`、`packages/py-core`、`tools/`、`testdata/`）；TypeScript 5.7 / React 18.3 / React Router 7.18 / Vite 8.3（`apps/web`、`packages/ts-api`）

**Primary Dependencies**: FastAPI、Pydantic v2、httpx（BFF）；OpenMetadata Server 2.0.3、`openmetadata-ingestion` 与 `openmetadata-managed-apis` 2.0.3（从子仓库 `ctx/2.0.3` 构建）；Apache Airflow 3.3.2（官方 Helm Chart，KubernetesExecutor）；Keycloak（令牌交换）

**Storage**: 正本在 OpenMetadata（PostgreSQL `openmetadata` 库 + OpenSearch）；调度状态在 Airflow（PostgreSQL `airflow` 库）；DAG 与生成配置在 Airflow 共享卷；BFF 仅有 002 的 `bff_sessions`，**零新增表**

**Testing**: pytest（单元、OpenAPI 契约、`-m cluster` 真实依赖集成）、vitest + Testing Library（组件）、Playwright（端到端与 1280 / 768 / 390 视口）；断言基于 003 金标准与 viewlab 标准答案

**Target Platform**: Kubernetes（本地 kind 三节点，StorageClass `rancher.io/local-path`；阿里云 ACK）

**Project Type**: Web application（`apps/web` + `services/bff`）+ 平台组件配置（`deploy/`）+ 镜像构建（`third_party/openmetadata/build`）

**Performance Goals**: 数据源列表与目录读取 p95 ≤ 2s；接入到首采完成 ≤ 3 分钟（SC-002）；测试连接与运行等待时长阶段 A 实测后写入 acceptance.md（research R11）

**Constraints**: 只读采集、零业务行复制；BFF 不持有源库密码、不直连源库、不直连 Airflow；浏览器只调 BFF；新增 / 修改代码行覆盖率 ≥ 80%

**Scale/Scope**: 5 类连接器（MySQL、PostgreSQL、Oracle、SQL Server、Doris）；实测基线 MES / QMS / Doris（28 张表 / 198 字段）与 viewlab（MySQL、PostgreSQL）；Oracle / SQL Server 无本地实例，以契约与单元测试覆盖并在 acceptance.md 注明

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*（宪法 v2.2.0）

| 条款 | 结论 | 依据 |
| --- | --- | --- |
| I 测试驱动 | PASS | 契约测试 → 失败测试 → 实现；集成测试用真实 OM / Airflow / 模拟库（`-m cluster`）；提交顺序保留测试先行 |
| II 微服务与契约优先 | PASS | 不新增服务；先改 `contracts/openapi/bff.yaml`（增量见 contracts/openapi.yaml）并生成 `packages/ts-api`；只调 OM 公开 REST，不读写 OM / Airflow 数据库 |
| III 开源优先与许可 | PASS | 复用 OM 原生采集与编排；`openmetadata-ingestion` / `managed-apis` 为 CCL 1.0，ADR-0011 第 4 节已批准私有化与内测例外。组件清单见下表 |
| IV 最小权限与审计 | PASS | BFF 以用户委托令牌调用 OM（RFC 8693，受众收窄到 `contexture-openmetadata`），OM 按用户角色授权并自动脱敏密码（research R5）；写操作留存含 trace_id / tenant_id / user_id 的审计日志；密钥只在 Secret |
| V 可观测性 | PASS | BFF 新路由复用 `contexture_core.telemetry`；OM 调用带 trace 传播 |
| VI 以服务集成、定制分级 | PASS | 全部为配置（Helm values、Keycloak 与 OM 配置）与镜像构建；本期无需官方扩展点与补丁（Doris UNIQUE KEY 不做）；如阶段 A 发现必须改上游，按“扩展点 → 补丁”并登记 `PATCHES.md` |
| VII 数据模型复用 | PASS | 零新增实体；数据源、任务、运行、测试连接、目录、血缘、治理全部用 OM 原生实体（data-model.md）；统计与继承标注为运行内投影 |
| 部署约束（Phase 1 单租户） | PASS | 不涉及多租户；本地共享卷采用节点固定、ACK 用 NAS，仅 values 差异 |
| 开发流程：原型先行 | PASS | 原型 2026-11-06 / 07 按 OM 调整并确认，spec 已同步 |
| 开发流程：原型与真实数据边界（v2.2.0） | PASS | 原型只提供结构 / 交互 / 状态 / 文案；生产页面数据全部来自 OM / Airflow；BFF 与前端均无示例数据与失败回退；测试断言基于金标准；做不到的写入 acceptance.md |
| 开发流程：acceptance.md | PASS | tasks 最后阶段编写，含 Oracle / SQL Server 无实例、Doris UNIQUE KEY、按次日志不可用等已知限制 |

**Post-design re-check（Phase 1 后）**：契约、数据模型与 quickstart 未引入新服务、新表或示例数据路径；结论不变，全部 PASS。

### 开源服务与组件清单（宪法 III）

| 组件 | 版本 | 许可 | 用途 | 部署单元 | 可替换方案 |
| --- | --- | --- | --- | --- | --- |
| OpenMetadata Server | 2.0.3（`2.0.3-ctx.0` 镜像） | Apache-2.0 | 数据源、采集任务、运行状态、目录、治理、血缘正本 | `openmetadata` | DataHub、Apache Atlas |
| Apache Airflow | 3.3.2 | Apache-2.0 | 采集任务调度与执行（ADR-0006） | `airflow` | Argo Workflows、Dagster |
| OpenMetadata Ingestion + Managed APIs | 2.0.3 | CCL 1.0（ADR-0011 例外） | 连接器、测试连接、元数据与视图血缘采集、DAG 部署接口 | `airflow`（织境 Airflow 镜像） | 自研采集（不采用） |
| Keycloak | 平台锁定版本 | Apache-2.0 | 用户身份与令牌交换 | `keycloak` | 其他 OIDC IdP |
| FastAPI / Pydantic / httpx | `uv.lock` 锁定 | MIT / BSD | BFF | `services/bff` | — |
| React / React Router / Vite | 18.3.1 / 7.18.2 / 8.3.4 | MIT | Web | `apps/web` | — |

## Project Structure

### Documentation (this feature)

```text
specs/005-source-metadata-ingestion/
├── prototype/            # 原型（结构 / 交互 / 状态 / 文案基准）与 OM 对齐记录
├── spec.md               # 规格（含 2026-11-07 澄清）
├── plan.md               # 本文件
├── research.md           # Phase 0：R1–R11 技术决策与出处
├── data-model.md         # Phase 1：OM 原生实体映射与投影规则
├── quickstart.md         # Phase 1：验证场景
├── contracts/openapi.yaml# Phase 1：BFF 增量契约（实施时合入 contracts/openapi/bff.yaml）
├── tasks.md              # Phase 2（$speckit-tasks 生成）
└── acceptance.md         # 实施收尾
```

### Source Code (repository root)

```text
third_party/openmetadata/build/
├── build.sh                          # 新增 airflow 目标：从子仓库源码构建织境 Airflow 采集镜像
└── Dockerfile.airflow                # 基于上游 ingestion/Dockerfile.ci 方式；连接器限五类

deploy/
├── components/airflow/values/        # 镜像、SimpleAuthManager 用户、basic_auth、dags.persistence、本地节点固定 / ACK NAS
├── components/openmetadata/values/   # pipelineServiceClientConfig.enabled=true、jwtTeamClaimMapping
├── components/keycloak/config/contexture.yaml  # bff 客户端增加 OM 受众与角色声明 mapper
└── charts/bff/                        # 新增 OM 受众等配置项

tools/
├── om_config.py                      # 幂等创建 OM 团队 admin / ai-engineer 与采集角色、策略
└── up.sh                             # 构建 / 导入织境 Airflow 镜像

testdata/
├── deploy/{mes,qms}/                 # 只读元数据账号；viewlab 库、视图与受限账号
├── mockfactory/…                     # viewlab 建库与标准答案（表级 / 字段级血缘）
└── tests/cluster/                    # viewlab 与只读账号的集群校验

contracts/openapi/bff.yaml            # 合入 005 增量
packages/ts-api/src/                  # 重新生成

services/bff/src/contexture_bff/
├── adapters/om_sources.py            # OM 数据源 / 采集任务 / 运行 / 日志 / 测试连接 / 目录 / 治理适配（用户委托令牌）
├── api/sources.py                    # /bff/v1/sources*
├── api/catalog.py                    # /bff/v1/catalog/*、/bff/v1/governance/options
├── main.py、settings.py              # 挂载路由；OM 受众配置
services/bff/tests/{unit,contract,integration}/

apps/web/src/
├── features/sources/                 # 列表、向导、详情、任务与运行、目录与属性编辑、API 封装
├── pages/SourcesPage.tsx
└── layout/{navigation.ts,SecondaryNav.tsx}   # “数据资产 → 数据源”入口与目录树
apps/web/test/ 与 tests/e2e/sources.spec.ts

docs/adr/0006-…、0011-…               # 更新：外部 Airflow 编排接口已采用；织境 Airflow 采集镜像
```

**Structure Decision**: 沿用现有 monorepo；不新增服务与包。首轮的 `extensions/om-ingestion/`（自研采集）不再创建——采集完全由 OM 原生框架完成。

## 实施阶段与闸门

| 阶段 | 内容 | 完成标志（闸门） |
| --- | --- | --- |
| A 基础设施 | 织境 Airflow 镜像；Airflow / OM / Keycloak 配置；OM 团队与角色；清理首轮遗留（Airflow 中 `contexture_om_dags.py` 与其 DAG） | 用 MES 真实走通：用户令牌测试连接 → 保存 → 部署 → 触发 → `PipelineStatus` 与最近日志可读；用户令牌读取服务时密码为掩码；research R5 的 3 个验证项有结论。**未通过不进入 C / D**；若 R1 不可行，回到负责人决策（ADR-0006 备选） |
| B 测试数据 | MES / QMS 只读元数据账号；viewlab（MySQL、PostgreSQL）与受限账号、标准答案 | `make mock-data` 后集群校验通过；PostgreSQL “不可读视图定义”可复现性有结论 |
| C BFF | 契约 → 契约测试 → 适配器与路由（红 → 绿） | 契约与集成测试通过；无示例数据路径（代码审查核对） |
| D Web | 按原型实现，数据全部来自 BFF | 组件测试与端到端通过；三种视口无溢出 |
| E 验收 | `make lint`、`make test`、`make e2e`；acceptance.md | 负责人手动验收 |

## Complexity Tracking

无违例项。

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| 无 | — | — |
