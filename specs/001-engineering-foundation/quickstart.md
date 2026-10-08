# Quickstart: 验证平台架构基座

用于验收 001 的三个用户故事。命令为目标形态，具体脚本在 tasks 阶段实现。

## 前置条件

- 本地单机 Kubernetes（kind）、Helm、uv、pnpm、Docker。
- 已克隆仓库并处于 `001-engineering-foundation` 分支。

## 1. 平台技术架构（用户故事 1）

1. 打开 `docs/architecture/platform-architecture.md`（由本特性产出，内容基于 plan.md“平台技术架构”）。
2. 从 `docs/Phase1-特性列表与开发计划.md` 任选 5 个特性，逐一在服务目录中确认：所属服务、独占存储、
   接口类型、依赖。
3. 确认 `docs/adr/0007` 至 `0010` 均已由“提议”改为“已接受”（0010 需确认 POC 平台后接受）。

**预期**：24 个特性全部有归属；每次查找不超过 5 分钟（SC-001、SC-002）。

## 2. 代码架构与公共库（用户故事 2）

```bash
cd services/bff && uv run pytest          # bff（参考实现）的单元、契约、集成测试
make components-check                     # 检查所有开源组件目录：清单、版本锁定、许可、离线镜像清单、冒烟测试
```

| 检查 | 预期 |
| --- | --- |
| 无令牌 / 过期令牌请求 `bff` | 401，错误体符合 `contracts/schemas/error.json` |
| 受众不符的令牌 | 403，`code = auth.invalid_audience` |
| 一次正常请求 | span 与日志带 `ctx.tenant.id`（部署常量）、`ctx.user.id`、`ctx.agent.id`（`contracts/otel/attributes.md`） |
| 经公共 MCP 取数客户端查询 | AI 网关审计中出现对应记录（含 `sub`、`azp`、`tenant_id`、工具）；`bff` 没有数据库账号 |
| `bff` 源码 | 不含自写的令牌验证、令牌交换、关联属性与错误格式代码 |
| 删除某组件 `component.yaml` 中的版本号 | `make components-check` 失败 |

**预期**：30 分钟内参照 `bff` 新增一个接口并跑通测试（SC-003、SC-004）。

## 3. 端到端骨架（用户故事 3）

```bash
make skeleton-up           # 在 kind 中部署（单租户）：Keycloak、OM（自建镜像）、Fuseki（OM 的 RDF
                           # 存储）、Doris、Airflow、OTel Collector、Langfuse、
                           # AI 网关、MCP Toolbox、bff、web
make skeleton-seed         # 在 OM 术语库预置“设备”对象及其属性并审批通过；
                           # 预置少量设备实例
```

1. 浏览器打开 `http://localhost:8080`，以测试用户登录。
2. 进入示例页面，查询对象类型 `equipment`。
3. 预期：显示“设备”对象类型的属性定义与设备实例（接口见
   `contracts/openapi/skeleton.yaml` 的 `bffListObjects`）。
4. 在追踪界面按本次 `trace_id` 查看：一条追踪包含 web → bff → AI 网关 → MCP Toolbox → Doris 与 bff → OM 的
   全部 span，每个 span 带相同的 `ctx.tenant.id`（部署常量，SC-005）。
5. 按本次 `trace_id` 查询 AI 网关的审计记录：可见一条 `read` 记录，含人（`sub`）、Agent / 服务（`azp`）、
   `tenant_id`、工具与查询摘要；返回行数可由 Toolbox / Doris 审计按同一 `trace_id` 查到。

## 4. 回归

```bash
make skeleton-test         # 运行骨架的端到端测试，公共库或组件版本升级时必须通过（FR-011）
```
