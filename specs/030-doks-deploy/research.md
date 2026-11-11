# Research: DOKS 云端开发与部署环境

**Feature**: 030-doks-deploy | **Date**: 2026-11-10 ~ 11 | **Spec**: [spec.md](spec.md)

所有集群事实来自 2026-11-10 用 `~/.kube/doks.yaml` 对目标集群的实测（只读查询与服务端试运行 `--dry-run=server`，未创建任何资源）；
仓库事实来自 `030-doks-deploy` 分支（基于 `main@104c55f`）；上游版本与许可来自 GitHub Releases / Repository API（2026-11-10 查询）。
标注 **【实测待验】** 的结论依赖实施阶段 Phase A 的验证任务，失败时按“回退方案”处理并回写本文件。

---

## R1 目标集群实测结果

| 项 | 实测结果 | 对方案的影响 |
| --- | --- | --- |
| 版本 / 区域 | DOKS v1.37.0，`sfo2`；上下文 `do-sfo2-k8s-1-37-0-do-3-sfo2-1794214302544` | 上下文名写入 `.env.cloud`（不入库） |
| 节点池 | 固定池 `primary-pool-1`：1 × `s-2vcpu-4gb`（可分配 1.9 核 / 2.9 GiB，min=max=1），devbox-0 在此；弹性池：min 0 / max 6，当前 0 节点（集群自动扩缩 `Healthy`） | 弹性池空闲时**确实缩到 0**（spec 假设成立）；织境负载须固定到弹性池（R7） |
| 弹性池名称 | 0 节点时无法从节点标签读出 | 作为配置项 `CTX_CLOUD_NODE_POOL`；`cloud-tools` 后用 `doctl kubernetes cluster node-pool list` 查询 |
| 权限 | 可创建 namespace、CRD、ClusterRole、Service | 满足 FR-030 等需求 |
| Pod 安全 | 所有 namespace 无 PSA 标签；无 Gatekeeper / Kyverno；`--privileged` 与 `seccomp/appArmor: Unconfined` 的 Pod 服务端试运行均通过 | 允许特权容器：BuildKit（R10）与 DinD（R12）可用 |
| 准入策略 | `doks-gateway-api-crd-protection`（禁止 UPDATE / DELETE 带 `doks.digitalocean.com/managed=true` 的 7 个 Gateway API CRD）；`gateway.cilium.io`（仅约束 `cilium` GatewayClass）；`deny-system-rbac-deletion`、`warn-on-node-deletion`；DO CCM admission webhook | 见 R2 |
| 预装 CRD | Gateway API **v1.6.1 standard**（DOKS 托管）、Cilium 全套、VolumeSnapshot；GatewayClass `cilium` 已存在 | Envoy Gateway 不得改写 Gateway API CRD（R2） |
| 存储类 | `do-block-storage`（默认）、`-retain`、`-xfs`、`-xfs-retain`，均为 RWO | 有状态组件用默认类；Airflow 共享卷见 R6 |
| LoadBalancer | 当前无 LB Service | 新建 1 个（R3） |
| 网络 | Cilium（含 kube-proxy 替代）；devbox 可解析集群 DNS | 集群内访问公网域名走 LB IP 时由 Cilium 直接转发（R5，【实测待验】） |

---

## R2 Gateway API CRD 与 Envoy Gateway

- **Decision**：继续使用 Envoy Gateway（与本地一致，保留入口追踪 `EnvoyProxy.telemetry`，ADR-0001），**不修改、不接管** DOKS 托管的 Gateway API CRD。
  gateway-helm 把 CRD 放在 Chart 的 `crds/` 目录，Helm 只在首次安装时创建**不存在**的 CRD、已存在的跳过且从不升级，因此不会触发 DOKS 的保护策略；
  Envoy Gateway 自身的 CRD（`gateway.envoyproxy.io`）与 DOKS 未装的实验通道 CRD 会正常创建。
- **【实测待验】** Envoy Gateway v1.9.2（组件清单锁定版本）与 Gateway API v1.6.1 standard 的兼容性：Phase A 第一个任务即在集群中安装并跑 `envoy-gateway` 冒烟测试。
- **回退方案**：① 升级 Envoy Gateway 到支持 v1.6 的版本（走 001 组件清单升级流程，本地同步升级）；② 仍不兼容时改用集群自带的 Cilium Gateway 作为云端入口（需补齐入口追踪），记 ADR。
  **不采用**给 CRD 加 `doks.digitalocean.com/install-policy=external` 接管——会使集群升级时 DOKS 不再维护这些 CRD，影响集群中其他负载。
- **Alternatives considered**：直接用 Cilium Gateway（本地 kind 无 Cilium，两套入口实现不一致，入口 span 需另配）；Ingress-NGINX（项目已统一为 Gateway API）。

## R3 对外入口与负载均衡器

- **Decision**：`deploy/components/envoy-gateway/config` 的 `EnvoyProxy.envoyService` 参数化：本地默认保持 `NodePort 30080`（渲染结果不变），云端为 `type: LoadBalancer`，
  带 `service.beta.kubernetes.io/do-loadbalancer-name: contexture`、`do-loadbalancer-size-unit: "1"`、健康检查注解；Gateway 增加 `https`（443）监听器，
  按主机名引用 R4 签发的证书 Secret。HTTP（80）监听器只挂两条路由：ACME 校验路由（cert-manager 自动创建）与“全部重定向到 HTTPS”的 `HTTPRoute`（`RequestRedirect` 过滤器），
  路径更长的校验路由优先匹配，不受重定向影响。
- **主机名**（基础域名 `CTX_CLOUD_DOMAIN`，如 `ctx.example.com`）：织境 Web 与 bff 为 `<基础域名>`；`sso`、`om`、`langfuse`、`airflow`、`jaeger`、`prometheus`、
  `dashboards`、`gateway-admin`（AI 网关管理界面）为子域名。DNS 只需两条 A 记录：`<基础域名>` 与 `*.<基础域名>` → LB 公网 IP（`cloud-deploy` 输出）。
- **停止期间**（FR-037）：LB 保留，Envoy Pod 为 0，DO LB 无健康后端时直接返回 503，访问地址与 IP 不变。【实测待验：响应码与时延】
- **Alternatives considered**：每个组件一个 LB（费用 × 9）；DO LB 上终止 TLS（证书须上传到 DO，自动续期链路更长）。

## R4 证书签发

- **Decision**：cert-manager v1.21.x（Apache-2.0）+ Let's Encrypt ACME **HTTP-01**，使用 Gateway API 求解器（`gatewayHTTPRoute`，parentRef 指向 `contexture` Gateway 的 http 监听器），
  开启 cert-manager 的 Gateway API 支持；一张证书含全部主机名（SAN ≤ 100）。先用 staging 签发器验通再切 production（避免速率限制）。
  启动命令（FR-034）在证书 `Ready` 前不报告成功；cert-manager 随环境停止，启动后按到期时间自动续期（证书 90 天、提前 30 天续期）。
- **Alternatives considered**：DNS-01 通配符证书（要求域名托管在支持的 DNS 服务商并提供 API 令牌，spec 假设不要求）；手工上传证书（违反 FR-019 自动续期）。

## R5 集群内自带 Keycloak 与对外地址

- **Decision**：复用 `deploy/components/keycloak/chart` 已有的自带模式（`keycloak.enabled: true`，参照 `values/bundled-example.yaml`）：
  `hostname: https://sso.<基础域名>`；PostgreSQL `databases` 增加 `keycloak`；导入任务用自动生成的管理员账号（Secret `keycloak-admin`，FR-010）；
  `withTestUsers: true`（FR-009）；`publicUrl` / `omUrl` 改为云端地址，bff 客户端回调登记为 `https://<基础域名>`（FR-008、FR-021）。
- **受信 CA**：云端证书为公共 CA，`trustedCaSecret` 置空。bff、AI 网关与 Keycloak 导入任务的 Chart 已支持空值；OpenMetadata 的 truststore 初始化容器写在 `values/base.yaml`，
  云端参数用空的 `extraInitContainers` / `extraVolumes` 及不含 truststore 参数的 `OPENMETADATA_OPTS` 覆盖（Helm 列表整体替换）。
- **集群内访问公网域名**：bff、OM、AI 网关校验令牌时访问 `https://sso.<基础域名>`，解析到 LB IP 后由 Cilium 在集群内直接转到 Envoy，无需出公网。【实测待验】
  回退：在 CoreDNS 不可改的前提下，于各组件 values 增加 `hostAliases` 指向 Envoy Service 的 ClusterIP。
- **Alternatives considered**：继续使用 Paperclip Keycloak（spec 已排除）。

## R6 存储与 Airflow 共享卷

- **Decision**：有状态组件使用默认 `do-block-storage`（RWO），云端参数沿用本地 `local` 的容量。Airflow 的 DAG / 日志卷在本地靠 `nodeSelector: kubernetes.io/hostname` 把全部 Airflow Pod
  （含 KubernetesExecutor 任务 Pod）固定到同一节点（005 research R4）；云端节点名不固定，改为 **Pod 亲和**：Airflow 全部组件与任务 Pod 以 `requiredDuringScheduling` 亲和到
  `component=scheduler` 所在节点，并都带弹性池 `nodeSelector`。
- **【实测待验】** Airflow Chart 的全局 `affinity` 是否作用于 KubernetesExecutor 的任务 Pod 模板；若否，在 `podTemplate` 中补齐。单个 4 核 8 GB 节点可容纳 Airflow 全部 Pod（requests 约 1.5 GiB）。
- **Alternatives considered**：RWX 存储（DOKS 无托管 RWX；自建 NFS 增加组件）；Airflow 改为 git-sync DAG（OM 通过 API 生成 DAG 文件，需共享卷，改动大）。

## R7 负载只调度到弹性池

- **Decision**：helmfile 新增 `cloud` 环境，值 `nodeLabel` / `nodePool` 来自 `CTX_CLOUD_NODE_LABEL` / `CTX_CLOUD_NODE_POOL`（R19）；每个组件的 `values/cloud.yaml(.gotmpl)` 按其 Chart 的键注入
  `nodeSelector: {<nodeLabel>: <nodePool>}`（DOKS 为 `doks.digitalocean.com/node-pool: <池名>`）（OM、Langfuse、Airflow、OpenSearch、Doris、CNPG、Envoy Gateway、cert-manager 等 Chart 均提供 nodeSelector；
  自建 Chart 新增可选 `nodeSelector`，默认空，本地渲染不变）。`smoke-lib.sh` 的临时 Pod 在设置 `CTX_NODE_SELECTOR` 时附加 `--overrides`。
  `otel-collector-agent`（DaemonSet）同样只在弹性池运行。`cloud-status` 检查并报告不在弹性池上的织境 Pod。
- **Alternatives considered**：给固定池加污点（DOKS 系统组件与 devbox 需相应容忍，且池污点由 DO API 管理，影响面大）；准入控制器统一注入（新增 Kyverno 组件）。

## R8 镜像仓库与版本标识

- **Decision**：DOCR（`registry.digitalocean.com/<仓库名>`，配置项 `CTX_CLOUD_REGISTRY`）。集群拉取用只读令牌生成的 `kubernetes.io/dockerconfigjson` Secret `docr-pull`，
  由 `cloud-deploy` 写入各织境 namespace，并在自建 Chart、OM、Airflow Chart 的 `imagePullSecrets` 中引用；构建（流水线、BuildKit）用读写令牌。
  镜像标签：流水线构建 `git-<提交前 12 位>`；集群内构建 `ws-<提交前 12 位>`（工作区干净）或 `ws-<提交前 12 位>-<改动摘要前 8 位>`（含未提交改动），
  OpenMetadata 相关镜像沿用上游版本标签（`2.0.3-ctx.0` 等）。
- **Alternatives considered**：DO 控制台“集成镜像仓库”自动下发 Secret（作用于所有 namespace，不可控）；GHCR（需另配公开 / 私有拉取凭证，且宪法以云厂商镜像仓库为主）。

## R9 镜像流水线（GitHub Actions）

- **Decision**：新增 `.github/workflows/cloud-images.yml`，仅 `workflow_dispatch`（输入：分支或提交）。步骤：检出（含 `third_party/openmetadata/src` 子仓库）→ `docker login registry.digitalocean.com`
  （仓库 Secret `DIGITALOCEAN_REGISTRY_TOKEN`）→ 构建并推送 bff、web（`git-<sha>`）→ 对 OM 三个镜像先查询仓库，已有同版本标签则跳过，否则以 `CTX_REGISTRY=<DOCR>` 调用
  `third_party/openmetadata/build/build.sh` 构建并推送 → 全部成功后输出镜像清单；任一失败则不推送 bff / web 的 `git-<sha>` 标签之外的部分（构建与推送分步，最后统一推送）。
- 现有 `ci.yml` 不变（宪法 CI 门禁照旧）。
- **2026-11-11 补充（负责人决定：未完成的特性不合并到 main）**：GitHub 规定 `workflow_dispatch` 只有在流水线文件已位于默认分支时才能触发，
  特性分支上的新流水线无法手动运行。因此增加推送专用标签 `cloud-images/*` 的触发：GitHub 对标签推送读取该标签所指提交中的流水线文件，
  无需改动 main。由 `make cloud-images` 打标签并推送（须确认，工作区须已提交），检出 `inputs.ref || github.ref`；`on.push` 只列标签、不列分支，
  普通分支推送与合并仍不触发（FR-023）。标签保留在仓库中，用于追溯镜像来源。

## R10 集群内构建 bff / web

- **Decision**：BuildKit（moby/buildkit，Apache-2.0）。`contexture-build` namespace 中运行一个 `buildkitd` Deployment（特权模式，构建缓存放 20 GiB PVC），平时副本为 0；
  `cloud-build` 将其扩为 1、等待就绪，开发机上的 `buildctl` 以 `--addr kube-pod://<Pod>?namespace=contexture-build` 连接（经 kubectl exec 传输构建上下文），按仓库现有 Dockerfile 构建并推送 DOCR，
  随后用 helmfile 只更新 bff / web 版本并记录稳定版本（data-model），最后把 buildkitd 缩回 0。开发机只运行 `buildctl` 客户端（几十 MB 内存）。
  OpenMetadata 相关镜像不在集群内构建（FR-022）。
- **Alternatives considered**：Kaniko（GoogleContainerTools/kaniko 已于 2025 年归档，不再维护）；DevSpace / Skaffold 的集群内 BuildKit 构建器（依赖开发机上的 `docker buildx` CLI）；
  每次构建起一个 Job 并上传 tar 上下文（需自研上下文传输与缓存）；无特权 rootless BuildKit（可行，但需额外 seccomp / AppArmor 配置，集群已允许特权，先取简单方案）。

## R11 开发模式与文件同步

- **Decision**：DevSpace v6.3.x（devspace-sh/devspace，Apache-2.0，单个二进制）。`deploy/cloud/devspace.yaml` 定义 `bff`、`web` 两个开发目标：
  以 `imageSelector` 选中 helmfile 部署的 bff / web，**替换 Pod**（DevSpace 把原 Deployment 缩为 0，另起一个使用开发镜像的副本，结束后 `devspace reset pods` 恢复原 Deployment），
  双向同步源码目录（bff：`services/bff/src`、`packages/py-core/src`；web：`apps/web/src`、`packages/ui/src`、`packages/ts-api/src` 等），
  同步锁文件变更时在容器内执行 `uv sync` / `pnpm install` 后重载（US2 场景 4）。
  - bff 开发进程：`uvicorn contexture_bff.main:create_app --factory --reload`（Python 源文件变化即重载）。
  - web 开发进程：Vite 开发服务器监听 8080，HMR 经 Gateway 的 WebSocket 以 443 回连（`server.hmr.clientPort`、`allowedHosts` 由环境变量传入，本地默认不变）；
    `/bff` 路径仍由 Gateway 直接路由到 bff，Vite 的本地代理不参与。
  - 开发镜像：bff / web 的 Dockerfile 各增加一个**非末尾**的 `dev` 阶段（含 uv / pnpm 与依赖），由 `cloud-build --dev` 在集群内构建；默认构建目标仍为末尾阶段，本地与流水线镜像不变。
- `make cloud-dev` 包装 `devspace dev`，以 `trap` 在退出（含中断）时执行 `devspace reset pods`；异常退出后 `make cloud-dev-reset` 可单独恢复（FR-012）；
  状态记录在 `contexture-cloud-state` 中（data-model）。【实测待验：DevSpace 6.3 的 replace-pods 与 helmfile 再次 sync 的相互作用；同步延迟 ≤ 10 秒】
- **Alternatives considered**：Skaffold（Apache-2.0；以自己部署为中心，`dev` 结束时删除资源，不符合“恢复稳定版本”）；Tilt（Apache-2.0；构建依赖本地 Docker 或自定义构建，live_update 需镜像链路）；
  自研 `kubectl exec tar` + 轮询同步（可靠性与断线补齐需自研）。

## R12 集群内检查与测试

- **Decision**：每次 `cloud-lint` / `cloud-test` / `cloud-e2e` / `cloud-seed` / `cloud-mock-data` 在 `contexture-ci` namespace 创建一个一次性**工具箱 Pod**：
  - 主容器 `contexture/toolbox` 镜像（Python 3.12 + uv、Node 22 + pnpm、Playwright 浏览器依赖、kubectl / helm），由 `cloud-build --toolbox` 在集群内构建，Dockerfile 位于 `deploy/components/ci-toolbox/`；
  - 边车 `docker:dind`（特权）提供 Testcontainers 所需的 Docker API（`DOCKER_HOST=tcp://localhost:2375`），集成测试代码与本地完全相同（宪法原则 I：真实依赖）；
  - 源码上传：`git ls-files -z -co --exclude-standard` 列出的文件（含未提交改动、不含忽略文件与凭证文件）经 `kubectl exec -i … tar x` 传入；
  - 输出：`kubectl exec` 直接把命令输出流回终端并透传退出码；`trap` 在结束或中断时删除 Pod（FR-016）；
  - 缓存：`toolbox-cache` PVC（uv / pnpm / Playwright / DinD 镜像缓存），同一时间只允许一个工具箱运行（以固定 Pod 名互斥）；
  - e2e：工具箱使用 `contexture` namespace 内受限 RBAC 的 ServiceAccount 运行 `-m cluster` 测试；Playwright `baseURL` 改为读取环境变量（默认仍为 `http://localhost:8080`），云端指向 `https://<基础域名>`。
- **Alternatives considered**：集成测试改连云端环境中的真实组件（需改写测试夹具，本地与云端行为分叉，且测试数据会污染演示环境）；在开发机运行（资源不足，spec 已排除）。

## R13 启停实现

- **Decision**：`tools/cloud/lifecycle.sh`（bash + kubectl + jq），按依赖顺序处理 `contexture`、`mock-sources`、`contexture-build`、`contexture-ci` 及织境安装的
  `envoy-gateway-system`、`cnpg-system`、`doris-system`、`cert-manager` namespace：
  - **停止**：确认开发模式 / 构建 / 测试（FR-038）→ 记录每个 Deployment / StatefulSet 的副本数到注解 `contexture.io/stopped-replicas` → 依次缩容：自建与平台工作负载 →
    Doris（先把 `doris-operator` 缩为 0，再把 FE / BE StatefulSet 缩为 0，避免 operator 拉回）→ PostgreSQL（CNPG 声明式休眠注解 `cnpg.io/hibernation=on`，保留 PVC）→
    控制器（Envoy Gateway、cert-manager、CNPG、Doris operator）→ 等待弹性池节点数降到 0（集群自动扩缩约 10 分钟判定闲置），超时 25 分钟则列出仍在弹性池上的非 DaemonSet Pod（FR-033）。
  - **启动**：逆序恢复（控制器 → CNPG 解除休眠 → Doris → 平台与自建工作负载），按注解恢复副本数并删除注解；bff / web 恢复为稳定版本；等待就绪、证书 `Ready`，运行冒烟测试（FR-034）。
  - **幂等与中断恢复**：以注解是否存在判断“已停止 / 部分运行”；重复执行收敛到目标状态（FR-035）。
- **定时采集**：停止期间 Airflow 不运行，错过的调度不执行。**【待确认】** Airflow 对 `catchup=False` 的 DAG 在调度器恢复后会为“最近一个调度区间”创建一次运行，
  这可能与 spec 边界情况“不补跑停止期间错过的采集”冲突。Phase A 实测：若确会补跑最近一次，向负责人确认接受（修订 spec）或在启动时跳过该次运行。
- **Alternatives considered**：卸载再部署（慢且依赖幂等部署重建数据卷绑定）；DOKS 节点池直接缩到 0（Pod 处于 Pending 时集群自动扩缩会立即扩回）。

## R14 云端配置与凭证

- **Decision**：开发机仓库根目录 `.env.cloud`（`.gitignore` 已有 `.env.*` 规则覆盖，另提供 `.env.cloud.example` 入库），键见 [contracts/cloud-config.md](contracts/cloud-config.md)。
  集群内自动生成的密钥沿用 `tools/up.sh` 的“已存在不覆盖”规则，在 `tools/cloud/secrets.sh` 中以 bash + openssl 实现（开发机无 Python；Fernet 密钥用 `openssl rand -base64 32 | tr '+/' '-_'`）。
  **不修改 `tools/up.sh`**：避免影响本地行为（SC-007），少量重复由 `tools/cloud/` 承担。
- 需要 Python 的步骤（OpenMetadata 本体配置 `tools.om_config`、`tools.seed`、`mockfactory`）在 R12 的工具箱 Pod 中运行。

## R15 开发机工具

- **Decision**：`make cloud-tools` 按 `tools/cloud/tools.lock`（名称、版本、下载地址、SHA256）把工具装到 `~/.local/bin`（持久卷，无需 root，FR-031）：
  kubectl、helm、helmfile、doctl、devspace、buildctl（buildkit 发布包中的客户端）、jq。实施时锁定**发布满两周**的版本，候选（2026-11-10 查询）：
  kubectl v1.37.2、doctl 2.4.0（已安装并校验）、helm v4.3.x、helmfile v1.8.x（v1.8.3 发布于 2026-11-06，尚不满两周，取此前补丁版本）、devspace v6.3.21、buildkit v0.34.x 中满两周者。
  helmfile 与 helm 的大版本须与本地开发者使用的一致，Phase A 以 `helmfile -e local template` 对比确认。
- `make lint`、`make test` 在缺少 uv 的机器上执行时提示改用 `cloud-lint` / `cloud-test`（FR-001a）。

## R18 开发机重启（devbox-0 Pod 重建）后的有效性

- **Decision**：开发机上需要保留的东西都放在主目录持久卷（`/home/vscode`，DO 块存储 PVC）上；根文件系统是临时的，不在上面存任何东西。
  | 内容 | 位置 |
  | --- | --- |
  | 仓库、`.env.cloud` | `~/workspace/OntoContexture/` |
  | 工具（含 `jq`） | `~/.local/bin/`（`cloud-tools` 安装；PATH 在 `~/.bashrc` 中） |
  | kubeconfig、doctl 登录 | `~/.kube/doks.yaml`、`~/.config/doctl/` |
  | DevSpace 状态 | `~/.devspace/` 与仓库内 `.devspace/`（加入 `.gitignore`） |
  | 云端命令日志 | `~/.cache/contexture/logs/`（不写 `/tmp`） |
  | 环境状态、Secret、数据、构建缓存 | 集群内的 ConfigMap / Secret / PVC，与开发机无关 |
- `git`、`curl`、`openssl`、`tar` 来自 devbox 镜像；`cloud-tools` 与 `common.sh` 在启动时检查，缺失则以退出码 2 明确报错，不在执行中途失败。
- **重启时正在运行的命令**：本地进程中断后 `trap` 不会执行，因此：
  - 工具箱 Pod 与 BuildKit 使用固定名称，下次运行同类命令前先清理残留；`cloud-status` 报告残留；`cloud-stop` 一并清理。
  - 开发模式由集群内状态记录 `devMode.active` 标识，重启后 `cloud-status` 显示“开发模式（无本地进程）”，执行 `cloud-dev-reset` 恢复稳定版本，或再次执行 `cloud-dev` 继续开发。
  - `cloud-deploy`、`cloud-stop`、`cloud-start` 都可重复执行（FR-003、FR-035），重启后再执行一次即可收敛。
- **验证**：Phase D / E 各安排一次“命令执行中删除 devbox-0 Pod，重建后恢复”的手动验证，写入 acceptance.md。

## R19 可移植性：DO 专用值全部参数化

- **Decision**：脚本（`tools/cloud/`）与通用模板只使用标准 Kubernetes API 和开源组件的能力：ConfigMap 状态记录、副本数注解、缩扩容、CNPG 休眠、helmfile、cert-manager、BuildKit、DevSpace、工具箱。
  云厂商专用的值一律来自配置，不写死在脚本或通用模板中：
  | DO 专用项 | 参数化方式 | DOKS 取值 |
  | --- | --- | --- |
  | 节点池标签键 / 值 | `.env.cloud` 的 `CTX_CLOUD_NODE_LABEL` / `CTX_CLOUD_NODE_POOL` → helmfile 值 `nodeLabel` / `nodePool` | `doks.digitalocean.com/node-pool` / 弹性池名 |
  | 负载均衡器注解 | `deploy/components/envoy-gateway/values/cloud.yaml` 中的 `loadBalancer.annotations` 参数块 | `service.beta.kubernetes.io/do-loadbalancer-*` |
  | 存储类 | `.env.cloud` 的 `CTX_CLOUD_STORAGE_CLASS` → helmfile 值 `storageClass` | `do-block-storage` |
  | 镜像仓库与登录 | `CTX_CLOUD_REGISTRY` 与令牌；`docker login` 的服务器取自仓库地址 | `registry.digitalocean.com/<名称>` |
  | 节点池查询 | 只在 `cloud-tools` 的提示和文档中使用 `doctl`；脚本统计节点时用 `kubectl` 按标签选择 | — |
- 停止后释放节点依赖集群自动扩缩，这一机制各云通用；最小节点数需在云厂商控制台设置，属于前置条件。
- 效果：后续 029 阿里云 ACK 或其他 Kubernetes 只需新写一份参数（新的 `.env.<环境>` 与各组件的云端参数），`tools/cloud/` 的脚本与启停逻辑不变。
  本期只交付 DOKS 一套参数，不扩大到实际适配其他云（spec 范围不变）。
- **验证**：脚本单元测试与渲染测试中加入“通用模板 / 脚本中不出现 `digitalocean`、`do-block-storage`、`doks.` 字样”的检查（`values/cloud.yaml` 与 `.env.cloud.example` 除外）。

## R16 资源规划

- 云端参数以 `local` 为基线：平台组件 requests 约 15 GiB 内存 / 3 核；BuildKit（构建时）requests 1 GiB；工具箱（运行时）requests 2 GiB + DinD 1 GiB。
  合计峰值 requests 约 19 GiB，弹性池 6 × 4 核 8 GB 扣除系统预留后约 33 GiB，余量充足；limits 合计约 30 GiB，允许超售。
  单个 Pod 最大 limits 为 Doris BE 4 GiB，可放入单节点。

## R17a bash 行覆盖率与组件登记（来自 2026-11-11 analyze，负责人选定 kcov）

- **Decision**：bash 脚本的行覆盖率用 kcov 统计（宪法 I 要求新增与修改代码 ≥ 80%）。kcov 输出 cobertura XML，`tools/coverage_gate.py` 新增 `--cobertura` 输入，与 Python、前端覆盖率一起参与门禁。
  kcov 只安装在工具箱镜像与 CI 中（开发机不装）；它是 GPL-2.0，只作开发测试工具、不进入交付物，在 `tools/license-allowlist.yaml` 的 `exceptions` 中登记（范围：仅 CI 工具箱与 CI 运行器，ADR-0014）。
- **Decision**：cert-manager、BuildKit、CI 工具箱按 001 的组件目录规范放在 `deploy/components/<组件>/`，带 `component.yaml`（版本、许可、镜像、冒烟测试），纳入 `make components-check` 与许可检查。
- **Decision**：`cloud-images` 流水线复用 `ci.yml` 中 syft / grype / trivy 的 SBOM、许可与漏洞扫描步骤，扫描不通过就不推送。
- **Alternatives considered**：bashcov（Ruby，需另装运行时）；把脚本逻辑改写为 Python（开发机没有 Python，需要在工具箱中执行，开发机侧仍要保留 bash 入口）。

## R17 宪法偏离与治理

- 宪法“部署约束”只写了阿里云 ACK / ACR 测试环境，并要求测试环境由流水线基于已合并提交部署；本特性在 DOKS 上新增开发 / 测试 / 演示环境，镜像可由任意分支手动构建，
  开发模式运行未提交代码。理由与处置见 plan.md 的 Constitution Check 与 Complexity Tracking：提交宪法 MINOR 修订（新增“DOKS 云端开发环境”条款），**在首次云端部署前**取得负责人批准；**已于 2026-11-11 获负责人批准（v2.3.0）**；
  新增 ADR-0014 记录云端开发环境的工具选型（R2、R10、R11、R12、R13）。

## 实施记录：R15 开发机工具（T007，2026-11-11）

`make cloud-tools` 在 devbox-0 上安装并校验通过：kubectl v1.37.2、helm **v3.22.1**（选 Helm 3 而非 4，与本地开发者常用大版本一致、风险更低）、helmfile v1.8.2、
doctl v2.1.0、devspace v6.3.21、buildctl v0.34.1、jq 1.8.2（均发布满两周，SHA256 与上游校验值一致；buildkit 无独立校验文件，取 GitHub 发布资产摘要）。
另装 uv 0.12.0（与 bff Dockerfile 一致）与 Python 3.12 到持久卷，仅用于在开发机上运行轻量的单元测试（`uv run pytest tools/tests` 约 2 秒，57 项）；
重的测试（集成、e2e、类型检查）仍按 R12 在工具箱中运行。helmfile 渲染的内存占用见 T016 记录。

## 实施记录：R2 Envoy Gateway 与 Gateway API（T017，2026-11-11 实测）

- **结论：兼容，无需回退。** Envoy Gateway v1.9.2 的 CRD 子 Chart 自带的 Gateway API 正是 **v1.6.1**（与 DOKS 预装版本相同）。
  `helmfile -e cloud -l name=envoy-gateway sync` 安装成功（约 3 分 47 秒，含弹性池从 0 扩到 1 个节点约 2 分钟）。
- DOKS 托管的 7 个 CRD 保持不变（`doks.digitalocean.com/managed=true` 仍在），未触发 `doks-gateway-api-crd-protection`；
  新增了 DOKS 未装的 6 个 CRD（listenersets、tcproutes、udproutes 及 3 个 `x-k8s.io` 实验 CRD），以及 Gateway API 的 `safe-upgrades.gateway.networking.k8s.io` 准入策略（由 Helm 管理，卸载时一并删除）。
- 控制器与 certgen 任务都调度在弹性池节点上（nodeSelector 生效）。certgen 第一次运行失败后重试成功，属上游已知的启动时序问题，不影响结果。
- 弹性池节点标签：DOKS 节点同时带 `doks.digitalocean.com/node-pool`（池名，弹性池为 `elastic-pool`）与 `node-pool-id`（UUID）；配置用池名或 ID 均可，本环境使用池名，配置项不变（R19）。

## 实施记录：R3 负载均衡器与停止时的响应（T019，2026-11-11 实测）

- Envoy 的 LoadBalancer Service 在约 1 分钟内获得公网 IP；HTTP 请求按重定向路由返回 `301 → https://…`。
- **集群内访问 LB IP**（开发机所在路径）由 Cilium 直接转发到 Envoy，往返约 9 ms（同时印证 R5：集群内访问公网域名不出集群）。
- **Envoy 缩为 0 时**：从集群内访问 LB IP 立即被拒绝连接（`curl` 返回码 000，耗时 < 1 ms），不会挂起；
  从公网经 DO 负载均衡器访问时，DO LB 在无健康后端时直接响应错误，该路径无法从开发机实测，列入 acceptance 由负责人在浏览器中验证。
- **重要发现**：Envoy Gateway 控制器重启后**不会**把 Envoy 代理 Deployment 的副本数从 0 拉回，必须由启动命令按停止前记录的副本数恢复（R13 的设计已覆盖，T080 实现时注意顺序：先恢复控制器，再恢复代理副本）。
- FR-037 据此改为“立即拒绝连接或返回错误响应，不长时间无响应”。

## 实施记录：R6 Airflow 共享卷与 Pod 亲和（T022，2026-11-11）

- **源码核实**（Airflow Chart 1.22.0，`files/pod-template-file.kubernetes-helm-yaml` 第 20–21 行）：KubernetesExecutor 任务 Pod 的
  `nodeSelector` / `affinity` 依次取 `workers.kubernetes.*`、`workers.*`、全局值；scheduler、api-server、dag-processor、triggerer、
  migrate / create-user 任务的模板均为 `or .Values.<组件>.affinity .Values.affinity`。因此只需设置**全局** `affinity` 与 `nodeSelector`，无需改 `podTemplate`。
- **方案**：全局 `podAffinity`（required，`topologyKey: kubernetes.io/hostname`）指向 `component=scheduler, release=airflow`。
  调度器自身匹配该选择器，按 Kubernetes 规则作为第一个 Pod 可直接调度；其余 Pod 随后落到同一节点，共享 RWO 的 dags 卷。
- 集群上的端到端验证（任务 Pod 与调度器同节点、能挂载 dags 卷）在 T052 首次完整部署后，以一次元数据采集运行确认，结论补记于此。

## 实施记录：R11 DevSpace 开发模式（T024，2026-11-11 实测，临时 namespace `ctx-probe`，已删除）

用一个由 Helm 部署的最小 Deployment 验证 DevSpace v6.3.21 的“替换 Pod + 同步 + 恢复”：
- **替换**：`labelSelector` 选中原 Pod（注意 `imageSelector` 与 `labelSelector` 不能同时使用），DevSpace 把原 Deployment 缩为 0，
  新建 `<名称>-devspace` Deployment 使用开发镜像，并在原 Deployment 上记录注解 `devspace.sh/replicas`。
- **同步延迟**：初始同步完成后，每次保存文件到容器内可见约 **0.9–1.3 秒**（含测量用 `kubectl exec` 的开销），满足 ≤ 10 秒（SC-002）。
  两次写入大小相同、间隔不足 1 秒时出现过一次约 47 秒的延迟（按修改时间与大小判断变化）；正常编辑间隔下未复现，记入 acceptance 已知限制。
- **中断后补齐**：暂停 devspace 进程 25 秒期间修改文件，恢复后 1.4 秒内补齐（spec 边界情况“网络短暂中断”）。
- **开发机内存**：devspace 进程常驻约 120 MB，开发机 2 GB 限额内可用（SC-003）。
- **退出不会自动恢复**：后台运行时 SIGINT / SIGTERM 不能结束 devspace（需 SIGKILL），且退出后原 Deployment 仍为 0 副本。
  因此 `cloud-dev` 必须在 `trap` 中先结束 devspace 进程，再执行 `devspace reset pods`；`reset pods` 实测能把原 Deployment 恢复为记录的副本数并删除 `-devspace` Deployment。
- **与 Helm 的相互作用（重要）**：替换期间执行 `helm upgrade`，Helm 会把原 Deployment 的副本数改回 Chart 中的值，原 Pod 与开发 Pod **同时运行**，Service 流量被两者分摊。
  因此 `cloud-deploy`、`cloud-build`（会更新 bff / web）在开发模式运行时，必须先确认（FR-013），确认后**先结束开发模式（reset pods）再部署**。

## 实施记录：R10 集群内构建与 R12 工具箱镜像（T030–T033，2026-11-11 实测）

- `buildkitd`（moby/buildkit v0.34.1，特权模式，20Gi 缓存卷）平时 0 副本；开发机 `buildctl --addr kube-pod://…` 直连成功。
- 不推送的试构建：bff 镜像 **17 秒**、web 镜像 **43 秒**、工具箱镜像 **93 秒**；构建上下文按 `.dockerignore` 上传，均不到 1 MB。满足 SC-004（≤ 10 分钟）。
- 推送凭证由开发机 buildctl 的一次性 `DOCKER_CONFIG` 提供（BuildKit 由客户端提供仓库认证），集群中的 `docr-push` 不再需要，仍保留以备后用。
- 推送到 DOCR、工具箱实际运行测试，待负责人提供镜像仓库后完成（T033、T038）。
