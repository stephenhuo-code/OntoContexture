# 手动验收：001 工程基座与交付流水线

- 依据：宪法 v1.6.0“每个特性交付手动验收文档”；spec 的“最终演示”6 步与 SC-001–SC-006
- 验收人：产品负责人（@stephenhuo-code）
- 预计用时：环境已就绪时约 60 分钟（第 1 部分 20 分钟、第 2 部分 15 分钟、第 3 部分 20 分钟、第 4 部分 5 分钟）；
  从零部署另加 30–40 分钟（首次拉取镜像）
- 每一步做完，在第 6 节记录表中填“通过 / 不通过 / 备注”。不通过的步骤请记下现象（截图或复制输出），我修复后复验。

## 0. 前置条件与数据准备

### 0.1 本机

| 项 | 要求 | 检查方式 |
| --- | --- | --- |
| Docker Desktop | 内存 ≥ 28 GB（Settings → Resources） | `docker info --format '{{.MemTotal}}'` ≥ 30000000000 |
| 工具 | kind、kubectl、helm、helmfile、uv、pnpm | `kind version && helmfile version && uv --version && pnpm --version` 均有输出 |
| Keycloak | Paperclip 的 Keycloak 与 Caddy 在运行 | 浏览器打开 <https://sso.127.0.0.1.nip.io/realms/digital-workforce/account> 能看到登录页 |
| `.env.local` | 仓库根目录存在，含 Keycloak 服务账号与客户端密钥（见根 `README.md`） | `grep -c = .env.local` ≥ 8 |

> Docker Desktop 重启后：① Paperclip 的容器不会自动启动，需先启动它们（Keycloak 在其中），如
> `docker start paperclip-postgres-1 paperclip-keycloak-1 paperclip-caddy-1 paperclip-litellm-1 paperclip-paperclip-1 paperclip-gateway-sync-1`；
> ② kind 集群会自动恢复，约 3–5 分钟后各服务就绪（`kubectl -n contexture get pods` 全部 Running / Completed）。

### 0.2 部署与示例数据

在仓库根目录执行：

```bash
make up        # 已部署过时可跳过；最后一行应为“==> 环境就绪：织境 http://localhost:8080”
make seed      # 输出三行：OpenMetadata：设备对象与 5 个属性（已审批）／bff：…／Doris：ctx_local.equipment 写入 10 行
make ports     # 另开一个终端窗口执行，保持运行；会打印各界面地址与 Langfuse 密码
```

### 0.3 测试账号

| 账号 | 密码 | 角色 | 用途 |
| --- | --- | --- | --- |
| `user1` | `user1` | 业务用户（business-user） | 最终演示 |
| `engineer1` | `engineer1` | AI 工程师（ai-engineer） | 可选：换账号重复第 1 部分 |
| `admin1` | `admin1` | 管理员（admin），也是 OM 管理员 | 查看 OpenMetadata 中的本体 |

> 你的 realm 是两步登录：先输用户名点“登录”，再输密码。

## 1. 最终演示（用户故事 3，SC-003）

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 1.1 登录 | 浏览器（建议无痕窗口）打开 <http://localhost:8080>，点“登录” | 跳转到 Keycloak 登录页（地址以 `https://sso.127.0.0.1.nip.io` 开头） |
| 1.2 | 用 `user1` / `user1` 登录 | 回到织境，地址为 `/objects/equipment`；右上角显示“User One · 租户 local”和“退出” |
| 1.3 会话安全 | 浏览器开发者工具 → Application → Cookies → `http://localhost:8080` | 只有一个 `ctx_session`，HttpOnly 勾选；Local Storage / Session Storage 中没有令牌 |
| 2.1 对象定义 | 看“对象定义（OpenMetadata，已审批）”表 | 标题“设备 Equipment”；表头上方 `urn:ctx:object:quality:Equipment`；5 个属性：code、name（必填“是”、数据级别“一级”）、model、line（“二级”）、installed_at（“三级”） |
| 2.2 对象列表 | 看“对象列表（Doris 本体实例库，经 AI 网关取数）”表 | 10 行，CNC-01 到 CNC-10；第一列对象 URI 形如 `urn:ctx:obj:local:Equipment:CNC-01`；底部“共 10 行 · 本次请求 trace xxxx” |
| 2.3（可选）定义来自 OM | 打开 <http://localhost:8585>，用 `admin1` 登录 → Glossary → `quality`（质量领域包）→ Equipment | 状态 Approved；Related Terms 中有 5 个 `hasProperty` 关系；Custom Properties 中 `ctx_kind = object` |
| 3.1 全链路追踪 | 复制页面底部的 trace 编号；打开 Jaeger <http://localhost:16686> → 顶部导航栏右侧的“Lookup by Trace ID…”输入框粘贴并回车 | 一条追踪，最上层 `contexture-gateway`（入口），其下 `bff`，再下 `agentgateway`（AI 网关）→ `mcp-toolbox`；`bff` 下另有访问 `openmetadata` 的 HTTP span（bff 缓存对象定义 5 分钟：若看不到 OM 的 span，执行 `kubectl -n contexture rollout restart deploy/contexture-bff`，约 30 秒后重新登录刷新页面，用新的 trace 编号再查） |
| 3.2 租户一致 | 在 Jaeger 中逐个点开 span，看 Tags | 每个 span 都有 `ctx.tenant.id = local`；bff 与 agentgateway 的 span 有 `ctx.user.id`（与 2.1 登录用户一致）、`ctx.agent.id = contexture-bff` |
| 3.3（可选）Langfuse | 打开 <http://localhost:3000>，用 `make ports` 打印的账号登录 → 项目“织境” → Tracing，按 trace 编号查找 | 同一条追踪，User 为该用户的 ID |
| 4.1 网关审计 | 终端执行 `tools/demo.sh audit <trace 编号>` | 打印一条记录：人（sub）为用户 ID、用户名 `user1`；调用方 `contexture-bff`；租户 `local`；工具 `list_objects`；参数 `{"type_key": "equipment", "limit": 20}`；返回行数 10 |
| 5.1 未登录调用 | 终端执行 `tools/demo.sh auth-check` | ① 无令牌：HTTP 401，错误体 `{"code":"auth.invalid_token","message":"缺少令牌","trace_id":"…"}` |
| 5.2 受众不符 | （同上命令的第二段输出） | ② HTTP 403，`{"code":"auth.invalid_audience","message":"令牌受众不符",…}` |
| 5.3 退出 | 回到浏览器点“退出” | 回到登录页；再打开 <http://localhost:8080/bff/v1/me> 返回 401 |
| 6 CI 拦截 | 见第 3 部分 3.4 | — |

## 2. 仓库与公共库（用户故事 1，SC-001）

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 2.1 测试 | `make test` | 最后一行 “N passed”，无 failed；“Required test coverage of 80.0% reached” |
| 2.2 代码检查 | `make lint` | ruff、pyright（0 errors）、eslint、prettier 均通过 |
| 2.3 前端测试 | `pnpm --filter @contexture/web test` | “Tests 4 passed” |
| 2.4 新增接口（SC-001） | 在独立的工作副本中演练，不影响主工作区：`git worktree add ../ctx-drill -b drill/sc-001` 后进入 `../ctx-drill`，执行 `uv sync --all-packages`；计时开始；按 `services/bff/README.md`“新增一个接口”的 4 步，新增 `GET /bff/v1/object-types/{typeKey}/attributes`（只返回属性列表）：改契约 → 写测试 → 实现 → 运行测试；计时结束 | ≤ 30 分钟测试通过；新增代码中没有令牌验证、追踪、错误处理代码（只用 `current_context` 依赖和公共库的异常）。做完后回到主仓库，执行 `git worktree remove --force ../ctx-drill && git branch -D drill/sc-001` 清理（只删除演练用的工作副本与分支） |

> 2.4 检验的是开发体验，也可以交给一位不熟悉本仓库的开发者来做，更能检验 SC-001。

## 3. 一键部署、CI 门禁与离线安装（用户故事 2，SC-002 / SC-004 / SC-005）

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 3.1 一键部署（SC-002） | （可选，耗时）`make down && make up`，记录开始与结束时间 | 最后输出各组件 ✔（airflow、doris、envoy-gateway、fuseki、jaeger、keycloak、langfuse、mcp-toolbox、openmetadata、opensearch、opensearch-dashboards、otel-collector、postgresql、prometheus、ai-gateway、bff、web）与“环境就绪”；镜像已在本机时 ≤ 30 分钟。完成后重新执行 `make seed` |
| 3.2 部署验收 | `tests/e2e/test_up.sh` | 最后一行“部署验收通过” |
| 3.3 组件清单 | `make components-check`；`make patches-check` | “components-check: OK”；“patches-check: OK（omnigent, openmetadata）” |
| 3.4 CI 故意失败（SC-004） | `uv run pytest tools/tests/test_ci_gates.py -v` | 5 个用例 PASSED，其中 `test_agpl_dependency_is_blocked`、`test_component_without_version_is_blocked` 证明 AGPL 依赖与缺版本号均被拦截 |
| 3.5 | `uv run python -m tools.license_check tools/tests/fixtures/agpl-package/sbom.cdx.json; echo $?` | 输出“FAIL 禁止的许可：some-agpl-lib …”，最后一行 `1` |
| 3.6 | 打开 `.github/workflows/ci.yml` 浏览 | 有 python、web、patches、contracts（oasdiff）、images（SBOM、许可检查、Grype、Trivy）五组检查 |
| 3.7 离线安装（SC-005） | 阅读第 5 节记录；（可选，约 30 分钟）按其中的复验方式自己跑一遍 | 记录中 17 个组件全部 ✔ 与“离线安装验收通过” |
| 3.8 自带 Keycloak | `deploy/components/keycloak/tests/smoke-bundled.sh` | 约 5 分钟后输出“keycloak（自带模式）OK” |
| 3.9 自动化回归 | `make e2e` | “12 passed”和浏览器测试“3 passed” |

## 4. 三项选型（用户故事 4，SC-006）

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 4.1 AI 网关 | 阅读 `docs/research/ai-gateway-spike/README.md` 与 ADR-0013 的“spike 结论” | 选定 agentgateway，4 项验证有结论与理由；Agent Router 只做了源码评估（已写明） |
| 4.2 Toolbox 连 Doris | 同上文档第 4 节 | 结论“可用”，并说明 `LIMIT` 改用模板参数 |
| 4.3 可观测后端 | 阅读架构文档第 8 节“已决”；打开 Prometheus <http://localhost:9090> → Status → Targets；OpenSearch Dashboards <http://localhost:5601> → Discover，新建索引模式 `ctx-logs*`，搜索 1.1 中的 trace 编号 | Prometheus 两个目标（otel-collector、ai-gateway）为 UP；Dashboards 能搜到 bff 带该 trace 编号的日志 |

## 5. 由我执行、需要你知晓的验证结果

| 项 | 结果 | 说明 |
| --- | --- | --- |
| 离线安装（SC-005） | 通过（2026-10-20） | 离线包 30 个镜像、9.7 GB；在断网 kind 集群中安装，17 个组件冒烟测试全部通过，见下方记录 |
| 模型网关 | 以 OpenAI 兼容的桩服务验证通过 | 你在 `.env.local` 配置 `MODEL_HOST`、`MODEL_NAME`、`MODEL_API_KEY` 并 `make up` 后，可用真实模型复验 |
| Agent Router | 未实际部署 | 只做源码 / 文档评估，理由见 spike 记录 |

离线安装记录（2026-10-20，`tests/e2e/test_offline_install.sh`）：

- 离线包：`make offline-package` 生成 `deploy/offline/dist/`（30 个镜像归档，按本机架构 linux/arm64 导出；10 个上游 Chart；部署文件副本）。
- 断网：新建 kind 集群 `contexture-offline`，节点 iptables / ip6tables 只放行集群内部与宿主机网段；验证节点访问 Docker Hub 失败后才开始安装。
- 安装：`deploy/offline/install.sh` 导入镜像、以离线 Chart 执行 helmfile；OM 本体配置写入成功。
- 冒烟测试：ai-gateway、airflow、doris、envoy-gateway、fuseki、jaeger、keycloak、langfuse、mcp-toolbox、openmetadata、opensearch-dashboards、
  opensearch、otel-collector、postgresql、prometheus、bff、web 全部 ✔，输出“离线安装验收通过”。
- 过程中发现并修复：kind 节点可经 IPv6 出网（验收脚本补 ip6tables）；多架构镜像需按单一架构导出；Envoy 代理镜像改为按标签引用。
- 复验方式：停掉本机集群（`docker stop contexture-control-plane contexture-worker contexture-worker2`）后执行
  `tests/e2e/test_offline_install.sh`（约 30 分钟），完成后 `docker start` 上述三个容器。

## 6. 验收记录

| 部分 | 步骤 | 日期 | 验收人 | 结果（通过 / 不通过） | 发现的问题 |
| --- | --- | --- | --- | --- | --- |
| 1 最终演示 | 1.1–1.3 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
|  | 2.1–2.3 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
|  | 3.1–3.3 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
|  | 4.1 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
|  | 5.1–5.3 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
| 2 仓库与公共库 | 2.1–2.3 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
|  | 2.4（SC-001） | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
| 3 部署与 CI | 3.1 | 2026-10-21 | @stephenhuo-code | 通过 | 首次重建时镜像下载超过 15 分钟，Langfuse、Airflow 超时；已改为预先导入本机镜像、等待时限 30 分钟（不属于验收缺陷） |
|  | 3.2–3.6 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
|  | 3.7 | 2026-10-20 | Claude（执行）／@stephenhuo-code（确认记录） | 通过 | 见第 5 节 |
|  | 3.8–3.9 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |
| 4 三项选型 | 4.1–4.3 | 2026-10-21 | @stephenhuo-code | 通过 | 无 |

**结论**：001 手动验收通过（2026-10-21，@stephenhuo-code），可按宪法合并到 main。

## 7. 与用户故事、成功标准的对应

| 成功标准 | 用户故事 | 验收步骤 |
| --- | --- | --- |
| SC-001 新增接口 ≤ 30 分钟 | US1 | 2.4 |
| SC-002 一键部署 ≤ 30 分钟（不含镜像下载） | US2 | 3.1、3.2 |
| SC-003 最终演示 6 步通过 | US3 | 第 1 部分（1.1–5.3）、3.4 |
| SC-004 CI 故意失败用例被拦截 | US2 | 3.4、3.5、3.6 |
| SC-005 离线安装包在断网 kind 中安装成功 | US2 | 3.7、第 5 节 |
| SC-006 三项选型有结论并写入文档 | US4 | 第 4 部分 |

## 8. 已知限制（不影响本次验收）

- 浏览器端不产生追踪；链路从入口网关开始（`contexture-gateway`）。
- OM 内置 MCP 接受交换后令牌、Omnigent 的委托令牌续期：分别在 009、014 验证。
- 阿里云测试环境在 004 之后搭建，届时按本文档复演。
- CI 尚未在 GitHub 上实际运行（仓库未推送）；门禁命令已在本地等价验证。
