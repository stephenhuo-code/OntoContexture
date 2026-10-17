# Quickstart: 验收 001 工程基座

对应 spec 的 4 个用户故事与“最终演示”。命令为目标形态，具体脚本在 tasks 阶段实现。

## 前置条件

- 本地：kind（在 Docker 中运行的 Kubernetes）、Helm、uv、pnpm、Docker Desktop（内存不足 64 GB 时用 `values-lite.yaml`）。
- 外部 Keycloak：`https://sso.127.0.0.1.nip.io`，realm `digital-workforce`；导出 Paperclip Caddy 的根证书供集群信任（见 `deploy/kind/README.md`）。
- 使用负责人现有的 Keycloak（与 Paperclip 同一 realm），`make up` 时增量导入织境的客户端与角色；没有 Keycloak 的环境用 `--set keycloak.enabled=true` 随织境部署；模型服务 key 由负责人自行配置。阿里云测试环境在 004 之后搭建。

## 1. 仓库与公共库（用户故事 1）

```bash
make test                                   # 仓库骨架、公共库、bff、web 的全部测试
cd services/bff && uv run pytest            # bff 单元、契约、集成测试
```

| 检查 | 预期 |
| --- | --- |
| 无令牌 / 过期令牌请求 `bff` | 401，错误体符合 `contracts/schemas/error.json` |
| 受众不符的令牌 | 403，`code = auth.invalid_audience` |
| 一次正常请求 | 日志与追踪带 `ctx.tenant.id`、`ctx.user.id`、`ctx.agent.id` |
| `bff` 源码 | 不含自写的令牌验证、令牌交换、追踪与错误格式代码 |
| 参照 `bff` 新增一个接口 | 30 分钟内测试通过（SC-001） |

## 2. 一键部署与 CI（用户故事 2）

```bash
make up                  # 在本地 kind 部署全部组件与 bff、web（SC-002）
make components-check    # 检查每个组件的清单、版本锁定、许可、离线镜像清单、冒烟测试
make offline-package     # 打离线安装包，再在断网 kind 中安装（SC-005）
```

CI 故意失败用例（SC-004）：加入一个 AGPL 依赖 → 失败；删除某组件 `component.yaml` 中的版本号 → 失败。


## 3. 最终演示（用户故事 3，SC-003）

```bash
make seed                # 在 OM 预置已审批的“设备”对象定义，在 Doris 预置少量设备数据
```

1. 浏览器打开织境 Web，用测试用户登录（跳转 Keycloak）。
2. 打开示例页面：看到“设备”的属性定义（来自 OM）与设备列表（来自 Doris）。接口见 `contracts/openapi/bff.yaml`。
3. 按本次 `trace_id` 查看追踪：web → bff → AI 网关 → MCP Toolbox → Doris，以及 bff → OM；每跳 `ctx.tenant.id` 相同。
4. 查看 AI 网关审计：人（`sub`）、调用方（`azp` = bff）、工具名、查询摘要、返回行数。
5. 用无令牌或受众不符的令牌直接调 `bff`：401 / 403，错误格式统一。
6. 触发 CI 的故意失败用例，确认被拦截。

在本地环境执行；阿里云测试环境在 004 之后搭建，届时复演一遍。

## 4. 三项选型（用户故事 4，SC-006）

| 选型 | 验证 | 结论写入 |
| --- | --- | --- |
| AI 网关 | ADR-0013 的 4 项验证（Toolbox 连 Doris、审计字段、模型网关、令牌受众） | ADR-0013 |
| Toolbox 连 Doris | 用 mysql 数据源执行示例查询工具 | ADR-0013 |
| 系统可观测后端 | 候选 Prometheus + Jaeger + OpenSearch Dashboards，部署并能查服务指标与日志 | 架构文档 |

## 回归

```bash
make e2e                 # 最小链路端到端测试；公共库或组件版本升级时必须通过
```
