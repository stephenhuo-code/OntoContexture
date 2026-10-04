# ADR-0001 Agent 轨迹与运行状态存储

- 状态：已接受
- 日期：2026-10-03
- 决策人：@stephenhuo-code
- 影响特性：001、002、005、008、009、010、017、019，二期自演进
- 相关宪法条款：II（状态外置）、III（开源许可）、IV（身份、审计、只用已审批内容）、V（可观测性）

## 背景

织境的决策轨迹（“用了哪些上下文 → 做了什么 → 人怎么改”）既是 P1 的验收项，也是二期自演进的
唯一输入。轨迹来自三处：客户侧 Agent 调用织境 MCP / Context API、织境内部 Agent、人对 Agent
输出的修改（如飞书中修改 8D 草稿）。

另外，织境内部 Agent（Omnigent，见 ADR-0002）需要在等待人工审批或进程重启后继续执行，必须保存运行状态。

讨论中出现过把两者混在一起的方案，需要明确：轨迹以哪里为准，运行状态放在哪里，两者是什么关系。

## 决策

### 1. Langfuse 是 Agent 轨迹的唯一真相来源

- 所有轨迹只经 OpenTelemetry Collector 写入 Langfuse，来源包括：织境服务端处理 MCP / Context API
  调用产生的 span、客户数字员工平台经 OTLP 回传的轨迹、织境内部 Agent 的 OTel 埋点、人的修改。
- 自演进、产品中的轨迹查询（按 NCR / 人 / Agent 查询）、纠正样本导出，都只从 Langfuse 读取。
  其他组件 MUST NOT 维护一份与之竞争的轨迹副本；统计结果、样本等派生数据 MUST 引用 `trace_id`。
- 每个 span MUST 携带以下关联信息（属性名在 001 的 OTel 规范中定稿）：

  | 信息 | Langfuse 字段 |
  | --- | --- |
  | 租户 | 每个租户对应一个 Langfuse project |
  | 人 | `user_id`（来自委托令牌） |
  | Agent | metadata `agent.id`（来自委托令牌） |
  | 运行 / 会话 | `session_id`，以及 `run_id` |
  | 业务对象 | tags 与 metadata，如 NCR 单号、指标 ID |
  | 引用的本体元素与口径 | observation metadata：本体 URI、口径 ID 与版本 |

- 人的修改：采纳、驳回、驳回理由写成 score；修改前后的完整内容写成同一 trace 下的
  “人工修订” observation（输入为原稿，输出为改后稿）。推给人的 Agent 输出（如飞书卡片）MUST
  携带 `trace_id`，修改回流时据此关联。
- 人审过的样本放入 Langfuse Datasets，按版本导出为 jsonl。
- 自演进生成的口径、提示词等提案 MUST 经织境审批中心批准后才生效；Langfuse 中提示词的生产标签
  只能由审批结果设置。
- 产品功能通过织境服务调用 Langfuse API，并先做授权求值；Langfuse 界面只供内部运维与标注使用，
  不直接开放给客户。

### 2. 运行状态以 rollout 记录保存，Phase 1 存 PostgreSQL

- 内部 Agent 每次运行的状态以 rollout 记录保存：只追加、每条一个 JSON 对象，格式与 `.jsonl`
  逐行一致（消息、工具调用、工具结果、审批请求、审批结果等事件）。Phase 1 存入 PostgreSQL，
  不写本地文件。
- 表结构（示意，以 plan 为准）：
  - `agent_run`：`tenant_id`、`run_id`、`trace_id`、人、Agent、状态（运行中 / 等待审批 /
    完成 / 失败）、租约持有者与到期时间（防止多个副本同时执行同一运行）。
  - `agent_rollout`：`run_id`、`seq`、`type`、`payload`（jsonb）、`created_at`；
    `(run_id, seq)` 唯一，保证追加原子、不重复。
- 在自然断点写检查点：每次模型响应、每次工具结果之后，以及遇到需审批的工具时运行结束之前。
- 恢复：读出 rollout，还原为会话的消息历史与待审批状态，审批结果传入后继续执行。Omnigent 现有
  运行状态只在 runner 进程内存中，rollout 的写入与恢复按 ADR-0002 作为改造项实现。
- rollout 与运行状态中 MUST NOT 保存令牌等凭证，只保存人、Agent、租户的身份引用；恢复时以 Agent
  服务身份代表该用户重新换取委托令牌，并按其当前权限重新求值（Keycloak 配置方式在 002 的 spike 中验证）。
- 有副作用的工具 MUST 幂等，幂等键为 `run_id` + 工具调用 ID，保证从检查点重跑时不会重复生效。
- 任一运行可导出为 `.jsonl` 文件，用于排障或迁移。
- 运行进入终态后保留 N 天再清理，N 在 plan 中确定。
- **rollout 不是轨迹**：自演进与轨迹查询 MUST NOT 读取 rollout。每条记录携带 `trace_id`，
  只用于和 Langfuse 交叉核对。

## 理由

- 轨迹只有一个来源，自演进和产品查询不会出现两份数据对不上的问题。
- Langfuse 已提供自演进需要的能力：轨迹、事后补写的评分（凭 `trace_id`，几天后也可）、
  标注、数据集、提示词版本管理、LLM 评估。官方说明这些功能自部署为 MIT 许可、无用量限制。
- Langfuse 的写入是异步的，允许延迟，不适合承担恢复执行这种强一致的状态，所以运行状态单独存放。
- 运行状态放数据库而不是本地文件，符合宪法 II 的服务无状态要求，也便于多副本、租户隔离与清理。
- rollout 采用 jsonl 逐行格式，后续换用持久化引擎时仍可作为导出格式。

## 影响

正面：
- 轨迹来源唯一，P1 验收中的“轨迹可按 NCR / 人 / Agent 查询”和二期自演进共用同一份数据。
- Phase 1 不引入持久化引擎，运行状态只依赖已有的 PostgreSQL。

负面与代价：
- Langfuse 成为客户生产环境的必装组件，连同其依赖（PostgreSQL、ClickHouse、Redis、
  S3 兼容对象存储，以所用版本的部署文档为准）一起进入交付包与离线安装包。
- 轨迹的可靠性取决于采集链路：Collector MUST 开启持久化发送队列与重试，Langfuse 不可用时
  轨迹不丢失。
- 跨大量轨迹的统计需要通过 API 批量导出后计算，Langfuse 不是分析数据库。
- Langfuse 企业版功能（SCIM、审计日志、数据保留策略）不使用；织境的授权审计由 005 负责。

## 考虑过的其他方案

| 方案 | 结论 |
| --- | --- |
| 轨迹存织境自己的存储（Doris + 图谱），Langfuse 只做观测 | 暂不采用：重复建设，且要自己做标注与数据集。若 Langfuse 的查询性能或权限控制不够，再把需要的数据抽取到 Doris |
| 用 Langfuse 同时保存运行状态 | 否决：写入异步，无法保证恢复执行所需的一致性 |
| rollout 写成 Pod 本地 `.jsonl` 文件 | 否决：Pod 重启或迁移即丢失，多副本并发写不安全，难以按租户隔离 |
| 现在就引入 DBOS 或 Temporal | 推迟：Phase 1 先用 rollout 检查点。二期出现多步、带定时等待和自动重试的流程时，优先评估 DBOS（只依赖 PostgreSQL），再考虑 Temporal |

## 后续工作

- 001：在 OTel 规范中定稿关联属性名；Collector 开启持久化队列；Langfuse 纳入 Helm 与离线包。
- 002 / 005：租户与 Langfuse project 的对应和开通流程；轨迹查询接口的授权求值。
- 009：按本 ADR 实现轨迹采集、人工修订写回、Datasets 导出。
- 019：推送到飞书的草稿携带 `trace_id`；spike 验证 Omnigent 的轨迹以 OTLP 进入 Langfuse 的呈现。
- 008 内部 Agent 运行时（见 ADR-0002）：在 Omnigent 中实现 `agent_run` / `agent_rollout` 与恢复逻辑。
