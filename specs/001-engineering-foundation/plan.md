# Implementation Plan: 平台技术架构与代码架构基座

**Branch**: `001-engineering-foundation` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-engineering-foundation/spec.md`

## Summary

为织境 Phase 1 的 24 个特性确定平台技术架构与代码架构，并以端到端骨架验证。

- **技术架构**：Phase 1 只自建 `bff` 一个后端服务 + 织境 Web + 管线任务镜像，其余复用 Keycloak、OM、
  Langfuse、Airflow、AI 网关、MCP Toolbox（ADR-0012、0013）；外部组件以服务方式集成；浏览器经 `bff` 用
  契约先行的 REST，Agent 与 `bff` 取数一律经 AI 网关以 MCP 访问；Phase 1 不引入消息中间件；跨切面能力由
  公共库 `contexture-core` 统一提供，边缘用 Gateway API 网关；令牌以 Keycloak 标准令牌交换得到
  （`sub` = 人，`azp` = Agent 或服务，受众收窄）。
- **代码架构**：monorepo（uv / pnpm workspace）；自建服务按需分层（`api`、`adapters` 必有）；开源组件每个一个
  标准目录（清单、Chart、参数、配置即代码与测试，CI 检查）；Phase 1 不做服务模板，`bff` 为参考实现（ADR-0009）。
- **单租户**：Phase 1 一套环境只服务一个客户（可有多个用户与 Agent），`tenant_id` 为部署常量（宪法 v1.5.0、
  ADR-0007 修订）。
- **四项待定决策**：多租户隔离（ADR-0007，已接受；Phase 1 按单租户执行）、本体六要素的定义与实现（ADR-0008：**不改 OM 核心；Phase 1 只做对象、关系、属性，直接使用 OM 的本体能力（术语库、审批、RDF / Fuseki），不另建本体服务**）、仓库结构
  与代码架构（ADR-0009）、数字员工平台（ADR-0010，待确认）。
- **端到端骨架**：web → bff → AI 网关 → MCP Toolbox → Doris，`bff` 经公共库 `ontology` 从 OM 读取已审批的对象定义；单租户部署。

决策依据见 [research.md](research.md)。

## Technical Context

**Language/Version**: Python 3.12（后端、管线）；TypeScript 5（前端）

**Primary Dependencies**: FastAPI、Pydantic v2、SQLAlchemy 2 + Alembic、httpx、OpenTelemetry SDK；前端按 ADR-0003（React 18、Vite、Tailwind、shadcn / Radix、TanStack Query）

**Storage**: PostgreSQL（每服务一个 database）；Doris（本体实例库 + 审计库）；OpenMetadata（本体定义与
元数据，含其 MySQL/PG、OpenSearch、Fuseki）；Langfuse（ClickHouse + Valkey + 对象存储）；对象存储
（测试环境 OSS / 离线 SeaweedFS）

**Testing**: pytest、Testcontainers、Schemathesis（契约）、oasdiff（破坏性变更）、Vitest / Playwright
（前端与骨架端到端）

**Target Platform**: 符合 CNCF 一致性认证的 Kubernetes（x86_64）；本地 kind、阿里云 ACK 测试环境、
发布验证环境

**Project Type**: 多服务 Web 平台（微服务 + Web 前端 + 管线）

**Performance Goals**: 骨架端到端 P95 ≤ 1 秒（本地）；AI 网关加 MCP Toolbox 的取数开销 P95 ≤ 100 毫秒（spike 中测定后确认）

**Constraints**: 宪法 I–VI 与部署约束；只用宽松许可组件；离线可部署；浏览器只访问 BFF

**Scale/Scope**: Phase 1 单工厂 POC；设计容量 500 个并发 Agent 运行；Phase 1 自建 1 个服务（`bff`）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 条款 | 检查 | 结论 |
| --- | --- | --- |
| I 测试驱动 | `bff` 含单元 / 契约 / 集成测试；组件配置即代码各带测试；骨架有端到端测试；公共库升级须骨架回归 | 通过 |
| II 微服务与契约优先 | 按能力域拆分，每个服务独占数据库并写明拆分理由；契约在 `contracts/` 先行，oasdiff 检测破坏性变更 | 通过 |
| III 开源与许可 | 全部组件为宽松许可；排除 MinIO（AGPL）、Redis（非宽松许可），改用 SeaweedFS、Valkey；开源服务清单见下文 | 通过 |
| IV 最小权限与审计 | Keycloak 标准令牌交换（`sub` = 人，`azp` = Agent，受众收窄）；公共库统一验签；数据层授权按 v1.5.0 的 Phase 1 例外推迟；AI 网关记录每次取数调用 | 通过（按例外） |
| V 可观测性 | 公共库注入关联属性，异步边界传递规则已定义；后端可替换 | 通过 |
| VI 以服务方式集成 | 外部组件均以独立服务集成；OM 与 Omnigent 以上游镜像仓库维护，OM 的 Phase 1 补丁仅 OKF v0.2（ADR-0012）；改动逐提交登记 | 通过 |
| 部署约束 | 同一套交付物覆盖三种环境；Phase 1 单租户，测试环境每套实例服务一个客户（v1.5.0 部署约束的 Phase 1 例外） | 通过（按例外） |
| 开发流程与质量门禁 | 门禁、多环境部署、离线打包在 tasks 准备阶段搭建（spec 已说明不作为用户故事） | 通过 |

无违反项，不需要 Complexity Tracking。

## 平台技术架构

完整架构见 [docs/architecture/platform-architecture.md](../../docs/architecture/platform-architecture.md)（本特性
FR-001 的产出，为唯一维护版本）。要点：

- **自建服务**：Phase 1 只有 `bff`，二期增加 `metric`、`explore`；另有前端 `web` 与管线任务镜像 `pipelines`
  （ADR-0012、0013）。
- **第三方底座**：OpenMetadata（从织境维护的仓库构建、独立部署，不改核心）、Keycloak、Langfuse、OTel
  Collector、Doris、Airflow、Omnigent（织境维护的仓库）、AI 网关（agentgateway 或 Agent Router）、MCP Toolbox、
  Envoy Gateway、PostgreSQL、OpenSearch、
  Fuseki、Valkey、对象存储。
- **关键约束**：实例与分析数据只经 AI 网关以 MCP 访问（数据管线写入 Doris 除外）；审批只用 OM 治理工作流；上下文复用 OM（OKF v0.2 补丁）；
  轨迹复用 Langfuse；管线在 Airflow；Phase 1 无消息中间件、不建服务网格、不做数据层授权。
- **待决事项**：系统可观测后端；OKF 补丁是否提交上游；Doris 表结构迁移的评审方式；AI 网关选型；ADR-0013 的
  5 项 spike 与其他待验证事项（见架构文档第 8 节）。

## 代码架构

见 ADR-0009（仓库结构、组件统一管理、服务内分层、公共库模块、契约规则）。本特性实现其中的公共库
`contexture-core` 全部模块的最小可用版本，骨架涉及的 `bff`、`web` 的最小版本，骨架涉及的开源组件目录
（Keycloak、OM、AI 网关、MCP Toolbox、Doris、OTel Collector、Langfuse）及其清单检查。

## Project Structure

### Documentation (this feature)

```text
specs/001-engineering-foundation/
├── plan.md              # 本文件
├── research.md          # Phase 0：架构决策
├── data-model.md        # Phase 1：跨切面模型与骨架模型
├── quickstart.md        # Phase 1：验收指南
├── contracts/
│   ├── openapi/skeleton.yaml
│   ├── schemas/error.json
│   ├── schemas/audit-event.json
│   └── otel/attributes.md
└── tasks.md             # /speckit-tasks 产出
```

另在仓库产出：`docs/architecture/platform-architecture.md`（平台技术架构）、`docs/adr/0007`–`0013`（代码架构即
ADR-0009，不另写文档）。

### Source Code (repository root)

本特性创建的目录（完整布局见 ADR-0009）：

```text
apps/web/                         # 最小外壳：登录 + 示例查询页面
services/
└── bff/                          # 最小版本：/bff/v1/me、示例查询（读 OM 本体 + 经 AI 网关调 MCP Toolbox）
packages/
├── py-core/                      # contexture-core：auth、telemetry、ontology、mcp、errors、tenancy、config
└── ts-api/                       # 由 contracts 生成的前端客户端
contracts/{openapi,schemas,otel}/ # 由本特性 contracts/ 拆分落位
agents/sample/                    # 示例 Agent：omnigent.yaml + registration.yaml（生成 Keycloak 客户端）
deploy/components/<组件>/          # 骨架涉及的组件：component.yaml、Chart、values、config、tests
                                  # （keycloak 的 realm 与客户端、ai-gateway 的路由与策略、toolbox 的示例查询工具等）
contracts/mcp/                    # 示例查询工具的 MCP 契约
deploy/helm/、deploy/terraform/aliyun/、deploy/offline/
extensions/                       # 空目录 + 说明（宪法 VI）
third_party/openmetadata/         # 织境维护的 OM 仓库（子仓库）+ UPSTREAM.yaml、PATCHES.md、build/（ADR-0011）
tests/e2e/skeleton/               # 骨架端到端测试
docs/architecture/
```

**Structure Decision**：采用 ADR-0009 的 monorepo 结构。骨架使用真实服务的最小版本（research R13），
后续特性在其上扩展，而不是丢弃重写。

## Complexity Tracking

无违反宪法的设计，不适用。

## Post-Design Constitution Re-check

完成 Phase 1 设计后复核：服务目录逐项写明独占存储与拆分理由（II）；契约已在 `contracts/` 定义（II）；
跨切面统一由公共库实现、审计失败即拒绝（IV）；关联属性与异步传递已规范（V）；对象类型改为不改 OM 核心
（VI）；所有组件许可合规（III）。结论：通过。

## 需要用户确认的事项

1. ADR-0008 改变了计划原假设：014 不再改 OM 核心，OM 为本体唯一来源；`third_party/openmetadata/` 为织境维护的 OM 仓库（子仓库），Phase 1 发布分支只含 OKF v0.2 补丁（ADR-0011、0012）。
2. ADR-0010 需确认 POC 客户实际使用的飞书 Agent 产品，以及能否携带用户令牌调用外部 MCP。
3. ADR-0009、ADR-0010 待评审（ADR-0007、0008、0011 已接受）。
4. 架构文档第 8 节的四项待决事项。
