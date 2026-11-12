# Data Model: DOKS 云端开发与部署环境

本特性不新增任何产品数据实体、数据库表或服务数据（宪法 VII）。下面只描述部署与运维用的元数据：其中一类存在开发机的配置文件里，另一类存在集群的 ConfigMap / 注解里。
它们都不属于织境的业务数据模型。

## 1. 云端环境配置（开发机 `.env.cloud`，不入库）

字段与校验规则见 [contracts/cloud-config.md](contracts/cloud-config.md)。所有 `cloud-*` 命令在修改集群前都会校验它（FR-004）。

## 2. 环境状态记录（集群 ConfigMap `contexture/contexture-cloud-state`）

| 字段 | 类型 | 说明 | 写入者 |
| --- | --- | --- | --- |
| `stableVersion.bff` / `stableVersion.web` | 镜像引用 | 最近一次部署的版本，即稳定版本 | `cloud-deploy`、`cloud-build` |
| `stableVersion.source` | `pipeline` \| `workspace` | 版本来源：流水线构建，或集群内基于工作区构建 | 同上 |
| `stableVersion.commit` | 40 位 SHA | 对应提交 | 同上 |
| `stableVersion.dirty` | bool | 构建时工作区是否含未提交改动 | 同上 |
| `stableVersion.deployedAt` | RFC 3339 | 部署时间 | 同上 |
| `omVersion` | 字符串 | OpenMetadata 相关镜像的版本 | `cloud-deploy` |
| `devMode.active` | bool | 是否处于开发模式 | `cloud-dev` 进入时写 true；退出或执行 `cloud-dev-reset` 时写 false |
| `devMode.startedAt` | RFC 3339 | 开发模式开始时间 | `cloud-dev` |
| `lifecycle.state` | `running` \| `stopping` \| `stopped` \| `starting` | 最近一次启停操作的目标状态 | `cloud-stop` / `cloud-start` |
| `lifecycle.updatedAt` | RFC 3339 | 最近一次启停操作的时间 | 同上 |

**状态转换**（`cloud-status` 报告的状态由 `lifecycle.state` 与实际副本数共同判定）：

```text
            cloud-deploy（首次）
                  │
                  ▼
running ──cloud-stop──► stopping ──（全部缩容，弹性池到最小值）──► stopped
   ▲                        │ 中途失败                               │
   │                        ▼                                       │
   └──（全部就绪＋冒烟测试通过）── starting ◄──────cloud-start───────────┘
                    （中途失败 → 部分运行；重复执行 cloud-start / cloud-stop 收敛到目标状态）

running 内部：stable ──cloud-dev──► dev ──退出 / cloud-dev-reset──► stable
```

- **部分运行**：`lifecycle.state` 为 `stopping` / `starting`，或实际副本数与目标状态不一致。
- 处于 `dev` 时执行 `cloud-deploy` 或 `cloud-stop`，须先确认（FR-013、FR-038）。

## 3. 停止前副本数（工作负载注解）

| 注解 | 所在对象 | 说明 |
| --- | --- | --- |
| `contexture.io/stopped-replicas` | 织境管理 namespace 内的每个 Deployment / StatefulSet | 停止前的副本数；启动时据此恢复，恢复后删除。注解存在即表示该对象处于停止状态 |
| `cnpg.io/hibernation` | CNPG `Cluster/pg` 及模拟库 QMS | CNPG 原生的休眠注解：`on` 为停止，删除注解即恢复 |

**织境管理的 namespace**：`contexture`、`mock-sources`、`contexture-build`、`contexture-ci`、`envoy-gateway-system`、`cnpg-system`、`doris-system`、`cert-manager`。
`dev`（devbox-0 所在）以及系统 namespace 永远不在处理范围内（FR-032）。

## 4. 镜像标签规则

| 来源 | 标签 | 例子 |
| --- | --- | --- |
| 流水线（bff / web） | `git-<提交前 12 位>` | `git-2d2d653a1b2c` |
| 集群内构建，工作区干净 | `ws-<提交前 12 位>` | `ws-2d2d653a1b2c` |
| 集群内构建，含未提交改动 | `ws-<提交前 12 位>-<改动摘要前 8 位>` | `ws-2d2d653a1b2c-9f3e01ab` |
| 开发镜像 / 工具箱镜像 | `dev-<依赖锁文件摘要前 12 位>` / `toolbox-<Dockerfile 与锁文件摘要前 12 位>` | 锁文件不变时复用 |
| OpenMetadata 相关 | 上游版本标签（如 `2.0.3-ctx.0`） | 同版本已存在时复用 |

**改动摘要**：对 `git diff HEAD` 与未跟踪且未忽略的文件内容做 SHA-256。同样的工作区得到同样的标签。
