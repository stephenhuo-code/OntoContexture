# Contract: 云端命令（`make cloud-*`）

所有云端命令的共同约定：
- 从开发机运行，开头先读取并校验 `.env.cloud`（见 [cloud-config.md](cloud-config.md)），失败时在修改集群之前退出，退出码 2。
- 只使用 `.env.cloud` 中的 kubeconfig、上下文和 namespace，不读写 kubeconfig 的当前上下文（FR-001a、FR-002）。
- 输出中不出现任何凭证值，只写凭证所在位置。
- 需要确认的操作：交互式终端里要求输入 `yes`；非交互环境下要求 `CONFIRM=yes`，否则退出码 3，不做任何改动。

- 日志写入 `~/.cache/contexture/logs/`（持久卷），不写 `/tmp`；开发机重建后，被中断的命令再次执行即可收敛，残留的工具箱 / 构建 Pod 由下次同类命令或 `cloud-stop` 清理（research R18）。

退出码：`0` 成功；`1` 执行失败（如冒烟测试、测试、构建失败）；`2` 配置或前置条件不满足；`3` 未确认；`4` 超时（如等待节点释放）。

| 命令 | 参数（make 变量） | 行为 | 需确认 | 对应需求 |
| --- | --- | --- | --- | --- |
| `cloud-tools` | — | 按 `tools/cloud/tools.lock` 把工具（含 jq）装到 `~/.local/bin`，并核对 SHA256；已装且版本一致的跳过；检查 git / curl / openssl / tar 是否存在 | 否 | FR-031 |
| `cloud-deploy` | `VERSION=git-<sha>`（默认取状态记录中的稳定版本；首次部署必填） | 生成缺失的 Secret → 用 helmfile 同步 `cloud` 环境 → 执行 OM 本体配置（工具箱）→ 冒烟测试 → 更新状态记录 → 输出访问地址、LB IP 与 DNS 记录 | 处于开发模式时需要 | FR-002～FR-010、FR-019～FR-021、FR-024、FR-028 |
| `cloud-info` | — | 输出各组件地址、登录方式与凭证所在 Secret 的名字和键（不输出值） | 否 | FR-029 |
| `cloud-status` | — | 输出运行状态（运行中 / 已停止 / 部分运行）、是否处于开发模式、稳定版本（来源、提交、是否含未提交改动）、弹性池节点数、不在弹性池上的织境 Pod | 否 | FR-036、R7 |
| `cloud-stop` | `TIMEOUT=25m` | 见 research R13；结束时输出弹性池节点数 | 有开发模式、构建或测试在运行时需要 | FR-032、FR-033、FR-035、FR-038 |
| `cloud-start` | `TIMEOUT=30m` | 见 research R13；bff / web 恢复为稳定版本；证书 Ready 且冒烟测试通过后输出访问地址 | 否 | FR-034、FR-035 |
| `cloud-dev` | `TARGET=bff\|web\|all`（默认 all） | 开发模式，前台持续运行并显示日志；退出或中断时恢复为稳定版本 | 否 | FR-011～FR-014 |
| `cloud-dev-reset` | — | 开发模式异常退出（含开发机重建）后，把 bff / web 恢复为稳定版本 | 否 | FR-012 |
| `cloud-build` | `TARGET=bff\|web\|all`；`--dev` / `--toolbox`（构建开发或工具箱镜像，不部署） | 基于当前工作区在集群内构建并推送；默认部署到环境，并成为稳定版本 | 否 | FR-022 |
| `cloud-images` | — | 为当前提交推送专用标签 `cloud-images/<提交前 12 位>`（连同当前分支）以触发 `cloud-images` 流水线，不访问集群；工作区有未提交改动或处于游离 HEAD 时以退出码 2 拒绝；远端已有该标签时提示已触发过、不重复推送；输出镜像标签 `git-<提交前 12 位>` 与查看运行的地址 | **需要**（会推送到远端仓库） | FR-023 |
| `cloud-lint` | — | 在工具箱中对当前工作区运行 `make lint` | 否 | FR-015、FR-016 |
| `cloud-test` | 透传 `PYTEST_ARGS` | 在工具箱中运行 `make test`（含集成测试，使用 DinD）与前端单元测试和覆盖率 | 否 | FR-015～FR-017 |
| `cloud-e2e` | — | 在工具箱中针对云端环境运行 `make e2e` 等价内容 | 否 | FR-018 |
| `cloud-seed` | — | 在工具箱中运行 `tools.seed` | 否 | FR-029 |
| `cloud-dev-metadata` / `cloud-dev-metadata-remove` | — | 在工具箱中导入 / 删除 006 的开发态元数据（对应本地 `make dev-metadata`；`cloud-e2e` 的资产搜索场景以此为前提） | 否 | FR-018 |
| `cloud-mock-data` | `MONTHS`、`SEED` | 部署模拟源系统，并重建模拟数据 | **需要**：先列出将被清空或重建的库 | FR-026 |
| `cloud-uninstall` | — | 删除织境管理的 namespace（含 PVC）和织境创建的集群级资源（Envoy Gateway / CNPG / Doris / cert-manager 的 CRD、GatewayClass `contexture`、ClusterRole）。不触碰 DOKS 托管的 Gateway API CRD、`dev` 以及系统 namespace | **需要** | FR-030 |

本地命令（`up`、`down`、`seed`、`e2e`、`mock-data`、`ports` 等）行为不变。`lint` 和 `test` 在找不到 `uv` 时，提示改用 `cloud-lint` / `cloud-test` 并以退出码 2 结束（FR-001a）。
