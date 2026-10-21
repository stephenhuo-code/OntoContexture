# AI 网关与 Toolbox 连接 Doris：spike 记录（001 T073–T077）

- 日期：2026-10-19
- 环境：本地 kind（`make up` + `make seed`），Keycloak 为负责人本机实例（realm `digital-workforce`）
- 结论：**选定 agentgateway v1.6.0**（Apache-2.0）；**Toolbox 1.14.0 的 mysql 数据源可直接连接 Doris 4.1.5**

## 1. 候选

| 候选 | 版本 | 部署形态 | 本次验证方式 |
| --- | --- | --- | --- |
| agentgateway | v1.6.0 | 单一进程，一份 YAML 配置（也有 K8s 控制器模式） | 在 kind 中实际部署（`deploy/components/ai-gateway/`），用真实令牌逐项验证 |
| Agent Router（原 Envoy AI Gateway，仓库 `theagentrouter/agent-router`） | v1.2.0 | Envoy Gateway 的扩展：控制器 + extproc 旁路容器，需修改 Envoy Gateway 的扩展管理配置 | **只阅读了源码与文档（v1.2.0 标签），未实际部署** |

## 2. ADR-0013 验证项

| # | 验证项 | agentgateway（实测） | Agent Router（源码 / 文档） |
| --- | --- | --- | --- |
| ① | 经网关调用 Toolbox 的 MCP 工具 | 通过：`list_objects` 经网关返回 Doris 数据（`deploy/components/ai-gateway/tests/test_policies.py`） | 支持（`MCPRoute` 聚合多个 MCP 后端） |
| ② | 审计记录 `sub`、`azp`、工具与查询内容 | 通过：访问日志以 CEL 增加字段，实测记录 `sub`、用户名、`azp`、租户、工具名、参数、返回行数、trace id；模型调用另有模型名与输入 / 输出 token | MCP 侧内置记录方法名、后端与参数；JWT 声明需经 Envoy 的声明映射到元数据再写入访问日志，链路更长 |
| ③ | 作为模型网关供 OpenAI 兼容客户端调用 | 通过（以 OpenAI 兼容的桩服务验证）：以 Keycloak 令牌调用 `/v1/chat/completions`，网关以厂商 key 转发、强制配置的模型；无令牌 401。真实服务商待负责人配置 key 后复验 | 支持（其主要场景） |
| ④ | 令牌受众校验 | 通过：无令牌 401；受众不是 `contexture-ai-gateway` 的令牌被拒绝 | 支持（`MCPRoute.securityPolicy.oauth`） |
| — | 开源版：按令牌声明的 token 配额、按模型授权、虚拟 key | 均具备（配置 schema 核实，未实测）：`localRateLimit`（`type: tokens`、`key: jwt.sub`）；`authorization` 规则可用 `llm.requestModel`；`apiKey` 认证 | 有按 token 的限流（`token_ratelimit` 示例）；按声明授权与虚拟 key 未核实 |

## 3. 选择 agentgateway 的理由

- 一个组件、一份配置即可同时承担 MCP 网关与模型网关，不需要改动已部署的 Envoy Gateway；离线包与升级更简单。
- 审计所需字段（人、Agent、工具、参数、行数、trace）直接用 CEL 写入访问日志，满足宪法 IV（Phase 1 例外：取数入口
  MUST 记录每一次调用），无需补丁或后端日志拼接。
- 原生 OTel 追踪，trace 与 bff、Toolbox 的 span 串联（ADR-0001）。

不足与后续：agentgateway 的访问日志写到 stdout；汇入可观测后端由日志采集完成（见 T079）。Agent Router 未实测，
若将来需要与 Envoy Gateway 深度集成再评估。

## 4. Toolbox 连接 Doris（T076）

- Toolbox 1.14.0 的 `mysql` 数据源连接 Doris 4.1.5 的 FE（9030 端口）可用：连接、参数化工具、只读账号 `ctx_reader` 均正常。
- **限制**：Doris 不支持在 `LIMIT` 中使用预编译占位符（`LIMIT ?` 报语法错误）。行数改用 Toolbox 的模板参数，
  以 `integer` 类型与 `minValue` / `maxValue`（1–100）约束；表名同样为模板参数，以 `allowedValues` 限定。
- Toolbox 1.x 的 SQL 工具每行返回一个文本块（JSON 对象），公共库 `contexture-core.mcp` 已按此解析。
- 不需要改用 Apache Doris MCP Server。

## 5. 未完成的验证

- Omnigent 以短期委托令牌作网关凭证并续期（ADR-0013 第 4 项后半）：Omnigent 在 014 接入时验证。
- OM 内置 MCP 接受交换后的令牌（第 5 项）：009 接入 OM MCP 时验证。
