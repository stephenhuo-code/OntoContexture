# 030 DOKS 云端开发与部署环境：验收文档

**状态：实施完成，待产品负责人手动验收。**

- 特性分支：`030-doks-deploy`（已推送；按负责人决定，全部特性开发完成前不合并到 main）
- 规格：[spec.md](spec.md)；计划：[plan.md](plan.md)；调研与实测记录：[research.md](research.md)（各“实施记录”小节）；命令契约：[contracts/cloud-commands.md](contracts/cloud-commands.md)
- 本文数字均来自 2026-11-11～11-12 在 DOKS 集群上的实测。

---

## 1. 前置条件

在开发机 devbox-0 的仓库根目录（`~/workspace/OntoContexture`）执行。

| 项目 | 检查方法 | 现状 |
| --- | --- | --- |
| kubeconfig | `kubectl --kubeconfig ~/.kube/doks.yaml get nodes` 能列出节点 | 已就绪；令牌 7 天过期，过期后在 DO 控制台重新下载 |
| 域名与 DNS | `getent hosts ctx.stephenwebsite.net` 与 `getent hosts sso.ctx.stephenwebsite.net` 都解析到负载均衡器 IP | Route 53 已配 `ctx`、`*.ctx` → 159.89.222.229 |
| 镜像仓库（DOCR） | `.env.cloud` 中已填写仓库地址与只读、读写令牌（文件权限 600，不进仓库） | `registry.digitalocean.com/contexture`（sfo2，Professional） |
| GitHub | 仓库 Secret `DIGITALOCEAN_REGISTRY_TOKEN`、Variable `CTX_CLOUD_REGISTRY` | 已配置 |
| 开发机工具 | `make cloud-tools` 显示“校验通过” | 已安装到 `~/.local/bin` |

## 2. 预计用时

约 90 分钟：访问与登录 10 分钟；开发模式 10 分钟；集群内检查与构建 25 分钟；启停 35 分钟（大部分是等待节点回收与扩容）；开发机重启验证 10 分钟。
可分次进行。环境当前为**运行中**；验收结束后如暂不使用，执行 `make cloud-stop` 释放弹性池。

## 3. 逐步验收

### 3.1 状态与访问（US4，SC-005）

```bash
make cloud-status
make cloud-info
```

预期：状态为“运行中”，当前版本为“稳定版本”；`cloud-info` 列出织境、Keycloak、OpenMetadata、Langfuse、Airflow 等子域名地址，不输出任何密码或令牌。

在任意联网电脑的浏览器中打开 <https://ctx.stephenwebsite.net>，用 `user1` / `user1` 登录，**用秒表记录从打开地址到看到首页的时间**。
预期：浏览器无证书警告，自动跳到 `sso.ctx.stephenwebsite.net` 登录，登录后进入首页，总耗时 ≤ 1 分钟（SC-005）。再逐个打开 `cloud-info` 列出的组件地址，均能打开。

```bash
bash tests/cloud/test_access.sh
```

预期：各子域名证书受信任、HTTP 重定向到 HTTPS、未登录跳转 Keycloak、模拟库端口不对外，最后输出“通过”。

### 3.2 开发模式（US2，SC-002、SC-003）

```bash
make cloud-dev
```

等出现“同步就绪”后，修改 `apps/web/src/i18n/zh-CN.ts` 中任一可见文字并保存，在浏览器刷新首页。预期：10 秒内看到改动。
按 `Ctrl+C` 退出后执行：

```bash
git checkout apps/web/src/i18n/zh-CN.ts
make cloud-status
```

预期：`cloud-status` 显示“稳定版本”，浏览器中页面恢复原样（5 分钟内）。实测：改动 1 秒内生效，开发模式进程 175 MiB，开发机工作集 1726 MiB（≤ 2 GiB）。

### 3.3 集群内检查、测试与构建（US3、US5，SC-004）

```bash
make cloud-lint
make cloud-test
make cloud-build TARGET=bff
make cloud-status
kubectl --kubeconfig ~/.kube/doks.yaml -n contexture-ci get pods
```

预期：`cloud-lint`、`cloud-test` 结果实时输出，退出码 0；`cloud-build` 10 分钟内完成，`cloud-status` 显示稳定版本来源为“工作区构建”并标明是否含未提交改动；
最后一条命令没有残留 Pod（`No resources found`）。实测见第 5 节。

### 3.4 启停（US6，SC-011、SC-012）

```bash
make cloud-stop CONFIRM=yes
make cloud-status
curl -s -o /dev/null -w '%{http_code}\n' -m 30 https://ctx.stephenwebsite.net/ || true
make cloud-start
```

预期：`cloud-stop` 20 分钟内结束并显示“弹性池节点：0”；`cloud-status` 显示“已停止”；停止期间访问立即失败（不挂起）；
`cloud-start` 30 分钟内结束，冒烟测试全部 ✔，最后输出访问地址；之后登录织境，005 接入的数据源与 OM 元数据仍在。
实测：停止 980 秒，启动 711 秒，数据前后一致，重复停止 / 启动直接成功。

### 3.5 开发机重启恢复（R18，T083，需负责人操作）

本项需要删除开发机 Pod，会中断当前终端，请在电脑上操作：

```bash
make cloud-dev          # 在开发机终端中保持运行
```

在电脑上执行（删除开发机 Pod，StatefulSet 会自动重建）：

```bash
kubectl --kubeconfig ~/.kube/doks.yaml --context do-sfo2-k8s-1-37-0-do-3-sfo2-1794214302544 -n dev delete pod devbox-0
```

重新连上开发机后执行：

```bash
make cloud-status       # 预期：当前版本显示“开发模式（无本地进程），执行 make cloud-dev-reset 可恢复”
make cloud-dev-reset
make cloud-status       # 预期：稳定版本
which kubectl helm helmfile doctl devspace buildctl jq   # 预期：全部位于 ~/.local/bin
```

另一种情况（工具箱残留）：执行 `make cloud-test` 期间删除开发机 Pod，重建后 `make cloud-status` 报告残留的 `pod/contexture-toolbox`，再次执行 `make cloud-test` 会先清理残留再运行。

### 3.6 本地不受影响（SC-007）

```bash
tools/cloud/tests/render-compare.sh
```

预期：local / lite 渲染与基线一致、cloud 渲染无本地地址、结构断言通过、无云厂商专用值泄漏，共 5 个 ✔。

## 4. 与用户故事、成功标准的对应

| 编号 | 内容 | 实测结果 | 记录 |
| --- | --- | --- | --- |
| US1 / SC-001 | 一条命令部署；重复部署 ≤ 20 分钟 | 20 个组件冒烟通过；重复部署 324 秒，Secret 不变；全新安装用时未单独测得（首次安装分 5 次完成） | research 首次完整部署（T052、T042） |
| US2 / SC-002、SC-003 | 开发模式即时生效；开发机 ≤ 2 GB | 1 秒生效；1726 MiB | research 开发模式（T075） |
| US3 / SC-004 | 集群内检查 ≤ 10 分钟 | cloud-lint 83 秒；cloud-test 596 秒；cloud-e2e 417 秒 | research 集群内测试（T068） |
| US4 / SC-005 | HTTPS 域名访问、1 分钟内登录 | 证书受信任、各子域名可达；浏览器登录耗时待负责人在 3.1 记录 | research R4 / R5、test_access |
| US5 / SC-004、SC-008 | 集群内构建 ≤ 10 分钟；流水线镜像 | cloud-build 85 秒；流水线约 30 分钟（OM 镜像版本不变时只构建 bff / web） | research T063、R9 |
| US6 / SC-011、SC-012 | 停止 ≤ 20 分钟、启动 ≤ 30 分钟、数据保留 | 980 秒 / 711 秒，数据一致，幂等；中断后收敛见第 5 节 | research 启动与启停幂等（T082） |
| US7 / SC-009 | 卸载 | **本轮未实测**（负责人 2026-11-11 决定跳过 T060） | — |
| SC-006 | 连续部署后数据保留 | 重复部署前后 user1 可登录、Secret 不变；连续 3 次部署的数据核对未单独执行 | research T042 |
| SC-007 | 本地渲染不变 | 通过 | render-compare |
| SC-010 | 无明文凭证 | 仓库、流水线日志、工具箱镜像扫描通过 | research T087 |

## 5. 自动化验证结论（T088，2026-11-12）

| 项目 | 结果 | 用时 / 说明 |
| --- | --- | --- |
| `make cloud-unit`（bash 单元测试） | 通过 | 开发机与工具箱中均全部通过 |
| `tools/cloud/tests/render-compare.sh`（SC-007） | 通过 | 5 项全部 ✔ |
| `make components-check` | 通过 | 组件清单与 Keycloak 主题副本一致 |
| `make cloud-lint` | 通过 | 83 秒 |
| `make cloud-test DIFF_BASE=main` | 通过 | 596 秒；Python 557 项、Web 147 项、UI 包 24 项、bash 单元测试全部通过；**变更行覆盖率 621/727 = 85.42%**（≥ 80%） |
| `make cloud-e2e` | **1 项失败** | pytest 部分 16 项通过；浏览器 25 项通过、1 项跳过、1 项失败：005 的“US1 接入 MES 并首采”（见第 7 节 A3）；`pnpm e2e:ui` 未运行（见 A1） |
| `tests/cloud/test_access.sh` | 通过 | 28 秒 |
| `tests/cloud/test_deploy.sh` | 通过 | 重复部署 326 秒；首轮因 DOKS 控制面接口断开（`cluster unreachable … EOF`）失败，重跑通过 |
| `tests/cloud/test_lifecycle.sh` | 通过 | 停止 980 秒、启动 711 秒、数据一致、幂等；另测中断后收敛 |
| `tests/cloud/test_toolbox_run.sh` | 通过 | 首轮发现删除后 Pod 残留约 30 秒、中断未真正生效，修正后通过 |
| `tests/cloud/test_dev_mode.sh` | 未重跑 | 11-11 已通过；本次开发模式代码未改动，且开发机内存已接近 2 GiB 上限，重跑有使开发机 OOM 的风险 |
| `tests/cloud/test_uninstall.sh` | 未执行 | 负责人决定本轮跳过（T060） |
| 远端 CI | 未运行 | CI 只在 PR 与推送到 main 时触发；030 按负责人决定不开 PR、不合并（见 A4） |

## 6. 已知限制

- **测试用户密码同用户名**（user1 / engineer1 / admin1），环境对公网开放，只能放模拟数据。
- **Jaeger、Prometheus、OpenSearch Dashboards、AI 网关管理界面没有登录保护**，并且对公网开放，所以只能放模拟数据。
- **Airflow 补跑**：调度器停止期间错过的调度点，启动后补跑一次（最近一个区间），负责人已接受（T023 / T086）。
- **开发模式期间不适合演示**：bff / web 是开发中的代码；开发模式期间执行部署会要求确认。
- **kubeconfig 令牌 7 天后过期**，需在 DO 控制台重新下载 `~/.kube/doks.yaml`。
- **本地 kind 只做了渲染对比**，没有在开发机上实际运行（开发机没有 Docker）。
- **kcov 属于许可例外**，只在开发测试中使用，不进入交付物（ADR-0014）。
- **OpenMetadata 三个第三方镜像的漏洞扫描只告警不阻断**（负责人 2026-11-11 决定）；结果随流水线产物留档。
- **启停命令之间没有互斥**：同时执行 `cloud-stop` 与 `cloud-start` 的结果不确定；任一命令被中断后，再执行一次目标命令即可收敛。
- **环境刚启动后的首次搜索可能超过 5 秒**：`assets.spec` US1 在启动后首轮失败、单独重跑通过；不影响功能。
- **`cloud-e2e` 中开发示例页用例（`pnpm e2e:ui`）在云端无法照原样运行**，见第 7 节。
- **005 的 MES 首采 e2e 偶发超时**（第 7 节 A3）。
- 卸载（US7）本轮未实测。

## 7. 待负责人决定

| 编号 | 事项 | 建议 |
| --- | --- | --- |
| A1 | `pnpm e2e:ui` 在工具箱中启动本地 Vite，云端登录 Cookie 属于织境域名，localhost 拿不到会话，无法照原样运行 | `cloud-e2e` 跳过该用例并提示原因；对应场景由开发模式验证（`tests/cloud/test_dev_mode.sh`）覆盖 |
| A2 | 已知不稳定用例（非 030 引入）：`demo.spec` 两个“设备”标题、006 建议接口的空白关键词契约、`column-locate` 滚动 | 另立任务在所属特性中修复 |
| A3 | 005 e2e“US1 接入 MES 并首采”偶发超时：Airflow 第一次尝试的 Pod 26 秒正常结束，任务却被标为 `up_for_reschedule`，约 2 分钟后第二次尝试成功，总耗时超出用例 5 分钟上限；同日另一轮通过（56.8 秒）。首次尝试的任务日志随 Pod 删除未保留 | 记入已知限制，另立任务（保留任务日志后复现定位） |
| A4 | 远端 CI 未运行 | 如需要，开一个不合并的草稿 PR 触发 CI |

## 8. 验收记录

| 步骤 | 结果（通过 / 不通过 / 未执行） | 备注 | 验收人 / 日期 |
| --- | --- | --- | --- |
| 3.1 状态与访问（含登录耗时） | | 登录耗时：____ 秒 | |
| 3.2 开发模式 | | | |
| 3.3 集群内检查、测试与构建 | | | |
| 3.4 启停 | | | |
| 3.5 开发机重启恢复 | | | |
| 3.6 本地不受影响 | | | |
| 第 7 节待决事项 | | | |
