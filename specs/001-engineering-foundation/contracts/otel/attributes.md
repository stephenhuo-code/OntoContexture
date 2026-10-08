# 可观测关联属性规范（v1）

所有服务的 span、结构化日志与审计记录 MUST 携带以下属性（ADR-0001、宪法 V）。由 `contexture-core.telemetry`
自动注入，业务代码不手工设置。

| 属性名 | 必填 | 说明 | Langfuse 映射 |
| --- | --- | --- | --- |
| `ctx.tenant.id` | 是 | 租户 | project（每租户一个） |
| `ctx.user.id` | 有人参与时 | 人（令牌 `sub`） | `user_id` |
| `ctx.agent.id` | 有 Agent 参与时 | Agent | metadata `agent.id` |
| `ctx.run.id` | Agent 运行时 | 一次运行 | metadata |
| `ctx.session.id` | 有会话时 | 会话 | `session_id` |
| `ctx.business.entity` | 有业务对象时 | 业务对象 URI 或单号（如 NCR 单号），可多值 | tags / metadata |
| `ctx.ontology.refs` | 引用本体或口径时 | 引用的本体要素 URI、指标 ID 与版本，可多值 | observation metadata |
| `ctx.token.id` | 是 | 令牌 `jti` | metadata |

## 异步边界

- HTTP：使用 W3C `traceparent` / `tracestate` 头传递；`ctx.*` 属性通过 W3C Baggage 传递。
- OM 事件回调：处理事件时以事件中的租户与实体信息恢复上下文，并新建关联的 span。
- Airflow 管线：DAG 运行配置携带 `tenant_id` 与 `traceparent`，任务启动时由公共库恢复上下文。

## 版本

属性名一经发布不得改名或改义，只允许新增；变更需更新本文件版本号并评审。
