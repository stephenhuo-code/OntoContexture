# ADR-0002 Agent 框架采用 Omnigent

- 状态：已接受
- 日期：2026-10-03
- 决策人：@stephenhuo-code
- 影响特性：001、002、005、006、007、008、019、024，二期自演进
- 相关宪法条款：II（服务边界）、III（开源许可、不长期深度分叉）、IV（身份与授权）、V（可观测性）
- 相关 ADR：ADR-0001（轨迹与运行状态存储）

## 背景

织境有两类 Agent：

- **客户侧 Agent**：作为织境的客户端，调用 MCP / Context API，验证身份与权限契约（019、024 的参考实现）。
- **织境内部 Agent**：织境自身的 Agent 能力。大部分场景需要真正执行 SQL 或数据处理管线
  （探索取数、口径校验、映射验证、数据质量检查、自演进分析），可能是多 Agent 系统，
  需要会话管理、并发、隔离执行与界面。

评估过的框架：Pydantic AI（MIT，轻量库，原生 OTel 与持久化执行对接，但会话、沙箱、界面需自建）、
Omnigent（Apache 2.0，工程化完整）、OmniAgent（GPL-3.0，排除）、Multica（附加条件限制嵌入与对外
托管，排除）、LangGraph（团队决定不用）。

## 决策

客户侧 Agent 与织境内部 Agent **统一采用 [Omnigent](https://github.com/omnigent-ai/omnigent)**。
团队熟悉其架构与界面，缺失能力由团队按需改造。

选择理由：Omnigent 已实现大量工程化能力——会话与服务端、YAML 定义 Agent 与子 Agent、MCP 工具、
策略（审批、工具调用次数、成本上限）、OIDC 登录、Web 界面、定时任务、以及沙箱提供者
（含 Kubernetes 与 [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)
及预热池）。这些用 Pydantic AI 都需要自建。

### 执行与沙箱

- **SQL**：一律经统一取数网关（006）执行：只读、授权求值、超时与扫描量上限、审计；Doris 按
  租户与 Agent 划分 workload group；管线需要写中间结果时，每次运行分配临时 schema，设配额并到期清理。
- **Python / 数据处理管线**：在沙箱中执行，沙箱层采用 agent-sandbox（Apache 2.0），配合 gVisor 或
  Kata（Apache 2.0）加固，经 Omnigent 的沙箱提供者接入。
- 沙箱内 MUST NOT 放数据库账号，取数一律经统一取数网关；每次执行注入短期委托令牌；网络策略只放行
  统一取数网关、对象存储与模型网关；限制 CPU、内存与时长；文件系统临时，产出物经对象存储带出；
  每次执行写入审计与轨迹。
- 云端沙箱服务（Modal、Daytona、E2B Cloud 等）MUST NOT 用于交付，客户云与离线环境只用自托管的
  K8s 沙箱。

### 需要改造或验证的能力

| # | 能力 | 现状（v0.16.0） | 处理 |
| --- | --- | --- | --- |
| 1 | 持久化执行 | 回合与 steering 状态只在 runner 进程内存（`omnigent/runner/app.py`），重启即丢；上游已移除 DBOS 设计 | 改造：按 ADR-0001 写 rollout 到 PostgreSQL，支持等待审批与重启后恢复 |
| 2 | 委托令牌透传 | 支持 OIDC 登录其界面；会话调用 MCP 时携带当前用户令牌未见文档 | 改造：每个会话、每次 MCP 调用与每次沙箱执行携带人 + Agent 的委托令牌；恢复时重新换取 |
| 3 | 多租户 | 有用户与邀请制，无租户概念 | 改造：Keycloak 租户映射到会话、Agent、沙箱、轨迹（Langfuse project）的隔离 |
| 4 | OTel 轨迹 | 文档未提 OpenTelemetry；自带匿名使用遥测 | 改造：以 OTLP 输出到 Collector，带 ADR-0001 规定的关联属性；**关闭对外遥测** |
| 5 | 并发规模 | 运行状态在进程内存，设计目标为团队协作 | 验证：Phase 1 压测 500 个并发运行；不足时改造 runner 水平扩展 |
| 6 | 离线与私有化模型 | 支持 OpenAI / Anthropic 兼容网关接 vLLM、Ollama 等 | 验证：断网环境 + 私有化模型跑通；选定内部 Agent 使用的执行器（harness），须支持私有化模型 |
| 7 | 界面融合 | Omnigent 自有完整 Web 应用 | 设计：以小补丁在 OpenMetadata UI 中挂载 Agent 面板（计划第 4 节前端方案 B），面板基于 Omnigent API |
| 8 | 版本与升级 | 0.x，约每周发版 | 锁定版本；每次升级跑完整回归后再跟进 |

### 改造方式（宪法 VI）

- 优先级：① 用 Omnigent 的扩展点（`omnigent.sandbox_providers` 入口、extensions、策略、YAML）；
  ② 向上游提 issue / PR；③ 本地补丁。
- 本地补丁集中在独立目录或分支，每个补丁登记：目的、对应上游 issue / PR、能否随上游升级删除。
- MUST NOT 长期维护深度分叉。若某项改造（尤其 #1 持久化）上游不接受且补丁持续增大，MUST 重新评估
  本 ADR，并按宪法修订流程记录例外。

## 影响

正面：
- 会话、界面、策略、沙箱编排、定时任务直接复用，内部 Agent 与客户侧 Agent 用同一套运行时。
- 团队熟悉架构，改造可控。

负面与代价：
- 持久化、委托令牌、多租户、OTel 四项改造落在 Omnigent 核心代码（runner 与服务端），与上游保持
  同步的成本较高；上游此前主动放弃了持久化设计，被接受的可能性低。
- 依赖 0.x 项目，接口变动频繁。
- 沙箱、统一取数网关、权限三层由织境自建，与框架无关。

## 考虑过的其他方案

| 方案 | 结论 |
| --- | --- |
| 内部 Agent 用 Pydantic AI | 不采用：会话、沙箱、界面、策略需自建，工程量大于改造 Omnigent |
| 内部 Pydantic AI + 外部 Omnigent 两套 | 不采用：维护两套运行时 |
| OmniAgent | 排除：GPL-3.0 |
| Multica | 排除：附加条件禁止嵌入商业产品与对外托管（含测试环境给客户使用） |
| LangGraph | 团队决定不用 |

## 后续工作

- 计划已新增两个 M1 特性（排在首个使用 Agent 的 010 之前）：
  - **007 执行沙箱**：agent-sandbox + gVisor / Kata、预热池、令牌注入、网络策略。
  - **008 内部 Agent 运行时**：部署 Omnigent，完成改造项 #1–#4、#6，压测 #5。
- 统一取数网关已前移到 M1 并改为 006：内部 Agent 在 P1 即需要经网关执行 SQL；由已审批指标生成 SQL
  的能力移到 020。
- 002 spike：Keycloak 中“Agent 服务身份代表用户换取令牌”的配置方式。
- 建立 Omnigent 补丁登记表与升级回归流程。
