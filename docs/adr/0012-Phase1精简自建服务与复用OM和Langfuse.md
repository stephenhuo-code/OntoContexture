# ADR-0012 Phase 1 精简自建服务：复用 OpenMetadata、Keycloak、Langfuse、Airflow

- 状态：已接受
- 日期：2026-10-07
- 决策人：@stephenhuo-code
- 影响特性：002、005、006、010、011、019、021、018、014、022
- 相关宪法条款：IV（Phase 1 例外，宪法 v1.3.0）、VI（上游镜像仓库与补丁登记）
- 修订：ADR-0001、0003、0005、0006、0007、0008、0011 中与本 ADR 冲突的内容以本 ADR 为准
- 被修订：`sql-gateway` 相关内容由 ADR-0013 取代（见文末修订）
- 依据：[OpenMetadata 能力调研](../research/OpenMetadata能力调研.md)（第 4、5、5b 节）

## 背景

架构评审时逐一核对了计划中的自建服务（`iam`、`gateway`、`graph`、`context`、`trace`、`ingest`）与
Keycloak、OpenMetadata、Langfuse、Airflow 的已有能力。原则是：先把已有框架的能力用好，不额外增加新的能力。

## 决策

### 1. 自建服务

| 原计划 | Phase 1 决策 | 由什么承担 |
| --- | --- | --- |
| `iam`（身份、授权、审计） | **取消** | 身份、角色、Agent 身份与令牌交换用 Keycloak；数据层授权推迟到二期（宪法 IV 例外）；取数审计由 AI 网关记录（ADR-0013） |
| `gateway`（统一取数网关） | **取消**（曾改名 `sql-gateway` 保留，后由 ADR-0013 取消） | 由 AI 网关（令牌、授权、审计）+ MCP Toolbox（只读查询）承担，均为开源组件 |
| `graph`（本体查询、追溯、实例搜索） | **取消** | 本体、元数据、血缘、搜索用 OM 的服务；对 Doris 中本体实例的追溯查询以 MCP Toolbox 的参数化工具经 AI 网关执行，本体映射经公共库 `ontology` 从 OM 读取 |
| `context`（MCP、Context API、上下文包） | **取消** | 复用 OM：资产 AI 上下文（`/v1/{实体}/{id}/context`）、上下文中心（文章、文件、记忆）、Persona 上下文、内置 MCP 服务 |
| `trace`（轨迹查询、修订写回、样本导出） | **取消** | 复用 Langfuse：界面与公开 API 按用户、会话、标签、元数据查询；人工修订由飞书同步管线经 Langfuse API 写回；样本用 Langfuse Datasets；织境 Web 的“决策轨迹”页面经 `bff` 调用 Langfuse API |
| `ingest`（飞书事件接收） | **取消** | 元数据采集复用 OM 采集框架与采集管道接口，部署到织境的 Airflow；飞书同步、实例物化等数据管线为 Airflow DAG，分钟级定时运行；用户可在 Airflow 中查看、触发、调度与运维，并可自定义管线 |
| `bff` | 保留 | 浏览器唯一入口；Omnigent 代理；本体读写（OM）；审批待办（OM 任务）；轨迹页面（Langfuse） |
| `metric`、`explore` | 二期 | 不变 |

Phase 1 自建服务只有 **`bff`**（ADR-0013 取消了 `sql-gateway`），另有前端 `web` 与管线任务镜像 `pipelines`。

### 2. 上下文交付复用 OM，OKF 升级到 v0.2

- 已核实：OKF 规范当前最新为 **v0.2**（`GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`，Apache 2.0）。
  OM 2.0.3 的资产 AI 上下文以“OKF 风格”的 Markdown 输出（`aicontext/AIContextMarkdown.java`），元数据字段为
  `type`、`title`、`description`、`fullyQualifiedName`、`resource`、`tags`、`timestamp`，属于 v0.1 写法。
- 与 v0.2 的差距：`timestamp` 应改为 `generated: {by, at}`；缺少来源 `sources`、可信度 `verified`、生命周期
  `status` 与 `stale_after`；只输出单篇文档，没有知识包结构（`index.md` 声明 `okf_version`、`log.md`）。
- **在织境维护的 OM 仓库中修改实现 OKF v0.2**（宪法 VI 上游镜像仓库方式）：改动提交在发布分支，登记于
  `third_party/openmetadata/PATCHES.md`；**是否提交上游待定**。v0.2 字段尽量使用 OM 已有数据填充（如审批状态、
  负责人、版本、生成时间）。
- 需验证：资产 AI 上下文是否包含未审批的术语与指标；若包含，在本补丁中按审批状态过滤或以 `status` 标注，
  满足宪法 IV“只用已审批内容”。

### 3. OM 内置 MCP 服务供客户 Agent 使用

- 修订 ADR-0011 的约定：OM 内置 MCP 服务（CCL）**允许在私有化交付中供客户 Agent 使用**，纳入已批准的 CCL
  例外（不对外提供与 Collate 竞争的在线服务）。
- 需验证：OM 配置 Keycloak 自定义 OIDC 后，MCP 能否直接接受 Keycloak 签发的委托令牌。

### 4. 授权与租户隔离（宪法 IV 的 Phase 1 例外）

- 授权只做到身份、租户与角色一级；数据层授权（数据级别、列级）推迟到二期。
- 经 OM 交付的上下文不做织境层面的租户隔离。测试环境为多租户共享实例，存在跨租户可见的风险；可选用 OM 自带
  的域访问策略（`DomainOnlyAccessPolicy`）做软隔离，不额外开发。
- 取数入口（AI 网关）记录每一次调用的审计（人、Agent、工具、查询摘要、返回行数，ADR-0013）。

## 理由

- 逐项核对后，取消的服务所承担的能力，Keycloak、OM、Langfuse、Airflow 都已具备或可以通过配置获得；剩余的
  执行查询（OM 开源版不具备）由开源的 AI 网关与 MCP Toolbox 承担（ADR-0013）。
- 管线由 Airflow 承载，用户可自定义与运维，比固定的接入服务更符合产品需要。
- 数据层授权与上下文租户隔离推迟到二期，符合 Phase 1 只读、单工厂 POC 的范围。

## 影响

- 宪法升到 v1.3.0（原则 IV 增加 Phase 1 例外）。
- OM 发布分支不再与上游完全一致：包含 OKF v0.2 改动。
- 二期引入写回、数据层授权或多客户正式交付前，须重新评估本 ADR 与宪法例外。
- 001 端到端骨架为：`web` → `bff` → AI 网关 → MCP Toolbox → Doris，本体定义经公共库 `ontology` 从 OM 读取。

## 修订（2026-10-08，见 [ADR-0013](0013-数据访问与AI网关.md)）

- **取消自建 `sql-gateway`**：Agent 取数一律经 MCP，由 AI 网关（agentgateway 或 Agent Router）统一校验令牌、授权、
  路由与审计，数据库后端用 MCP Toolbox。Phase 1 自建服务只剩 `bff`。
- 上文中由 `sql-gateway` 承担的查询审计，改由 AI 网关记录；追溯查询以 Toolbox 的参数化工具实现。
- 令牌：Agent 为 Keycloak 客户端，以标准令牌交换得到 `sub` = 人、`azp` = Agent 的令牌。
- 001 端到端骨架改为：`web` → `bff` → AI 网关 → MCP Toolbox → Doris。
