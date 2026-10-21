# Quickstart: 验收 001 工程基座

对应 spec 的 4 个用户故事与“最终演示”。命令均已实现并在本地验证（2026-10-19）。逐步的手动验收见 `acceptance.md`。

## 前置条件

- 本地：Docker Desktop（内存 ≥ 28 GB，不足时 `make up ENV=lite`）、kind、kubectl、helm、helmfile、uv、pnpm（Node 22）。
- 外部 Keycloak：负责人现有实例 `https://sso.127.0.0.1.nip.io`，realm `digital-workforce`（与 Paperclip 共用）。在该 realm 中
  建导入服务账号 `contexture-provisioner`（机密客户端，开启 Service account roles；`realm-management` 角色：manage-clients、
  manage-realm、view-realm、view-identity-providers、view-users、manage-users），凭证写入 `.env.local`（见根 `README.md`）。
  `make up` 增量导入织境的客户端、角色与测试用户，不改动已有配置。没有 Keycloak 的环境打开 `keycloak.enabled=true`。
- Paperclip 的 Caddy 容器 `paperclip-caddy-1` 运行中（集群信任其本地 CA，见 `deploy/kind/README.md`）。
- 模型服务 key 由负责人在 `.env.local` 配置（`MODEL_HOST`、`MODEL_NAME`、`MODEL_API_KEY`），未配置时模型路由为占位。

## 1. 仓库与公共库（用户故事 1）

```bash
uv sync --all-packages && pnpm install
make test                                   # Python 单元、契约、集成测试（集成测试启动 Keycloak、PostgreSQL 容器）
make lint                                   # ruff、pyright、eslint、prettier
pnpm --filter @contexture/web test          # 前端组件测试
```

| 检查 | 预期 |
| --- | --- |
| 无令牌 / 过期令牌请求 `bff` | 401，错误体符合 `contracts/schemas/error.json` |
| 受众不符的令牌 | 403，`code = auth.invalid_audience` |
| 一次正常请求 | 日志与追踪带 `ctx.tenant.id`、`ctx.user.id`、`ctx.agent.id`、`ctx.token.id` |
| `bff` 源码 | 不含自写的令牌验证、令牌交换、追踪与错误格式代码（均来自 `contexture-core`） |
| 参照 `bff` 新增一个接口 | 按 `services/bff/README.md` 的步骤，30 分钟内测试通过（SC-001） |

## 2. 一键部署与 CI（用户故事 2）

```bash
make up                  # kind 集群 + helmfile 部署全部组件与 bff、web，并运行各组件冒烟测试（SC-002）
tests/e2e/test_up.sh     # 部署验收：冒烟测试全部通过、Pod 均就绪、入口可达
make components-check    # 每个组件的清单、版本锁定、许可白名单、镜像可离线打包、冒烟测试
make patches-check       # third_party 发布分支相对上游的提交与 PATCHES.md 一致
make offline-package     # 离线安装包 deploy/offline/dist/
tests/e2e/test_offline_install.sh   # 断网 kind 中用离线包安装并就绪（SC-005）
deploy/components/keycloak/tests/smoke-bundled.sh   # 自带 Keycloak 模式
```

CI 故意失败用例（SC-004），本地等价验证：

```bash
uv run pytest tools/tests/test_ci_gates.py -v      # AGPL 依赖、缺版本号的 component.yaml 均被拦截
uv run python -m tools.license_check tools/tests/fixtures/agpl-package/sbom.cdx.json   # 退出码 1
uv run python -m tools.components_check tools/tests/fixtures/components-no-version     # 退出码 1
```

推送到 GitHub 后由 `.github/workflows/ci.yml` 执行同样的门禁（另含 SBOM、Grype、Trivy、oasdiff）。

## 3. 最终演示（用户故事 3，SC-003）

```bash
make seed                # OM：已审批的“设备”对象与 5 个属性；Doris：ctx_local.equipment 10 行
make ports               # 把 OM、Langfuse、Jaeger、Prometheus、OpenSearch Dashboards 转发到本机
```

1. 浏览器打开 <http://localhost:8080>，点“登录”，用 `user1` / `user1` 登录（跳转 Keycloak）。
2. 示例页面 `/objects/equipment`：看到“设备”的属性定义（来自 OM，已审批）与设备列表（来自 Doris）。接口见 `contracts/openapi/bff.yaml`。
3. 复制页面底部的 `trace` 编号，在 Jaeger（<http://localhost:16686>）中查询：入口网关 → bff → AI 网关 → MCP Toolbox，以及 bff → OM；
   每个 span 的 `ctx.tenant.id` 为 `local`。同一 trace 也在 Langfuse 中（项目“织境”）。
4. 查看 AI 网关审计：`kubectl -n contexture logs deploy/ai-gateway | grep <trace 编号>`，含人（`audit.sub`）、调用方
   （`audit.azp` = `contexture-bff`）、工具名、参数、返回行数。
5. 无令牌直接调 `bff`：`curl -i http://localhost:8080/bff/v1/me` → 401；受众不符的令牌 → 403。
6. CI 故意失败用例：见第 2 节。

自动化回归：`make e2e`（集群测试 + 浏览器演示）。阿里云测试环境在 004 之后搭建，届时复演一遍。

## 4. 三项选型（用户故事 4，SC-006）

| 选型 | 结论 | 记录 |
| --- | --- | --- |
| AI 网关 | agentgateway v1.6.0 | `docs/research/ai-gateway-spike/README.md`、ADR-0013 |
| Toolbox 连 Doris | mysql 数据源可用（行数以受约束的模板参数传入） | 同上 |
| 系统可观测后端 | Prometheus + Jaeger + OpenSearch Dashboards（日志经 OTel Collector 节点代理） | 架构文档第 8 节 |

## 回归

```bash
make e2e                 # 最小链路端到端测试；公共库或组件版本升级时必须通过
```
