# Contract: 云端配置（`.env.cloud`）与 helmfile `cloud` 环境

## `.env.cloud`（仓库根目录，被 `.gitignore` 的 `.env.*` 规则忽略；模板 `.env.cloud.example` 入库）

| 键 | 必填 | 例子 / 格式 | 校验 | 用途 |
| --- | --- | --- | --- | --- |
| `CTX_CLOUD_KUBECONFIG` | 是 | `~/.kube/doks.yaml` | 文件存在、权限为 600 | 所有 kubectl / helm 调用 |
| `CTX_CLOUD_CONTEXT` | 是 | `do-sfo2-…` | 该上下文在 kubeconfig 中存在，且能访问 API | 固定的集群上下文 |
| `CTX_CLOUD_NAMESPACE` | 否 | `contexture`（默认） | DNS-1123 格式 | 平台 namespace |
| `CTX_CLOUD_NODE_LABEL` | 是 | `doks.digitalocean.com/node-pool` | 合法的标签键 | 节点池标签键（R19） |
| `CTX_CLOUD_NODE_POOL` | 是 | 弹性池名称 | 非空 | 节点池标签值：节点固定（R7）与启停时的节点统计 |
| `CTX_CLOUD_STORAGE_CLASS` | 是 | `do-block-storage` | 集群中存在该存储类 | 有状态组件、构建缓存与工具箱缓存的 PVC（R19） |
| `CTX_CLOUD_DOMAIN` | 是 | `ctx.example.com` | 合法域名，不能是 `localhost`、`nip.io` 等本地地址 | 入口与证书（R3、R4） |
| `CTX_CLOUD_ACME_EMAIL` | 是 | 邮箱 | 格式正确 | Let's Encrypt 账号 |
| `CTX_CLOUD_ACME_SERVER` | 否 | `staging` \| `production`（默认 production） | 只能取这两个值 | 签发器 |
| `CTX_CLOUD_REGISTRY` | 是 | `registry.digitalocean.com/<名称>` | 非空 | 镜像仓库 |
| `CTX_CLOUD_REGISTRY_READ_TOKEN` | 是 | DO 只读令牌 | 非空，输出中不回显 | 集群拉取 Secret `docr-pull` |
| `CTX_CLOUD_REGISTRY_WRITE_TOKEN` | 是（用 `cloud-build` 时） | DO 读写令牌 | 同上 | BuildKit 推送 |
| `MODEL_HOST` / `MODEL_NAME` / `MODEL_API_KEY` | 否 | 与 `.env.local` 相同 | — | AI 网关模型路由 |

本地 `.env.local` 里的 `KEYCLOAK_PROVISIONER_*` 在云端不需要：自带 Keycloak 使用自动生成的管理员账号。`CONTEXTURE_BFF_CLIENT_SECRET` 和 `CONTEXTURE_OM_CLIENT_SECRET` 由 `secrets.sh` 自动生成并保存在集群中，不需要手工填写。

## 集群 Secret（由 `tools/cloud/secrets.sh` 生成，已存在则不覆盖，FR-003）

沿用 `tools/up.sh` 中的全部 Secret 名称与键，并新增：`keycloak-admin`（username、password）、`pg-keycloak`、`docr-pull`（dockerconfigjson，由 `cloud-deploy` 根据配置更新），
以及 `contexture-build` namespace 中的 `docr-push`。`ctx-trusted-ca` 在云端不创建。

## helmfile `cloud` 环境的值

| 值 | 来源 | 被引用于 |
| --- | --- | --- |
| `env: cloud` | 固定 | 选择 `values/cloud.yaml(.gotmpl)` |
| `domain` | `CTX_CLOUD_DOMAIN` | Gateway 监听器、HTTPRoute 主机名、Keycloak hostname、bff / OM / AI 网关的对外地址与回调 |
| `nodeLabel`、`nodePool` | `CTX_CLOUD_NODE_LABEL`、`CTX_CLOUD_NODE_POOL` | 各 release 的 nodeSelector |
| `storageClass` | `CTX_CLOUD_STORAGE_CLASS` | 各 release 的 PVC |
| `loadBalancer.annotations` | `deploy/components/envoy-gateway/values/cloud.yaml`（随云厂商不同而替换的参数块） | Envoy 的 LoadBalancer Service |
| `registry`、`bffTag`、`webTag`、`omVersion` | `.env.cloud`、`VERSION`、状态记录 | 镜像引用 |
| `acmeServer`、`acmeEmail` | `.env.cloud` | ClusterIssuer |

**不变约束**：`helmfile -e local template` 与 `helmfile -e lite template` 在本特性前后的渲染结果逐字节一致（渲染对比测试，SC-007）。
`helmfile -e cloud template` 的结果中不出现 `localhost`、`127.0.0.1.nip.io`、`ctx-trusted-ca`、`NodePort`（FR-021）。
