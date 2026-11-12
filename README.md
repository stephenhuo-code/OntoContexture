# 织境 OntoContexture

面向企业数字员工的上下文层：本体（OpenMetadata）、受控取数（AI 网关 + MCP Toolbox）、决策轨迹（Langfuse）。
架构见 `docs/architecture/platform-architecture.md`，决策见 `docs/adr/`，特性规格见 `specs/`。

## 快速开始（本地）

### 环境要求

- macOS / Linux，Docker Desktop **内存 ≥ 28 GB**（全量组件约 16 GB；不足时用 `make up ENV=lite`）
- 工具：`kind`、`kubectl`、`helm`、`helmfile`、`uv`、`pnpm`（Node 22）
- 身份：一个 Keycloak（≥ 26.2）。本机使用负责人现有的 Keycloak（经 Paperclip 的 Caddy，`https://sso.127.0.0.1.nip.io`），
  织境配置以增量方式导入，不影响已有客户端；没有 Keycloak 时设置 `keycloak.enabled=true` 随织境部署
  （见 `deploy/components/keycloak/`）

### 准备 `.env.local`（不进仓库）

```bash
KEYCLOAK_URL=https://sso.127.0.0.1.nip.io
KEYCLOAK_REALM=digital-workforce
KEYCLOAK_PROVISIONER_CLIENT_ID=contexture-provisioner     # realm 内的导入服务账号（见 quickstart）
KEYCLOAK_PROVISIONER_CLIENT_SECRET=...
CTX_PUBLIC_URL=http://localhost:8080
CONTEXTURE_BFF_CLIENT_SECRET=...                          # openssl rand -hex 32
CTX_OM_URL=http://localhost:8585
CONTEXTURE_OM_CLIENT_SECRET=...                           # openssl rand -hex 32
# 可选：模型服务（AI 网关的模型路由）
# MODEL_HOST=api.deepseek.com:443  MODEL_NAME=deepseek-chat  MODEL_API_KEY=...
```

### 部署与验证

```bash
make up        # 创建 kind 集群，部署全部组件与 bff、web，运行各组件冒烟测试（约 20–40 分钟，首次需拉取镜像）
make seed      # 示例数据：OM 中已审批的“设备”对象与属性；Doris 中 10 台设备
make e2e       # 端到端：AI 网关策略、Toolbox、全链路追踪与审计、浏览器演示
make ports     # 把 OM、Langfuse、Jaeger、Prometheus、OpenSearch Dashboards 的界面转发到本机
```

打开 <http://localhost:8080>，用 `engineer1` / `engineer1` 登录（`user1` 是业务用户，无织境 Web 权限），查看“设备”的定义与列表。

### 开发

```bash
uv sync --all-packages && pnpm install
make test      # Python 单元、契约、集成测试（集成测试需 Docker）
make lint      # ruff、pyright、eslint、prettier
pnpm --filter @contexture/web dev   # 前端开发服务器（/bff 代理到 localhost:8080）
```

新增一个后端接口的步骤见 `services/bff/README.md`。

## 云端开发与部署（DOKS，030）

在 DigitalOcean Kubernetes 上运行一套织境，兼作开发环境：开发机不需要 Docker，构建、测试都在集群内执行。
云端命令统一以 `cloud-` 开头，只作用于 `.env.cloud` 指定的集群，与上面的本地命令互不影响。
完整步骤见 [specs/030-doks-deploy/quickstart.md](specs/030-doks-deploy/quickstart.md)。

```bash
make cloud-tools                  # 安装 kubectl、helm、helmfile、doctl、devspace、buildctl、jq 到 ~/.local/bin
cp .env.cloud.example .env.cloud  # 填写集群、域名、镜像仓库（不进仓库）
make cloud-images                 # 触发 GitHub 镜像流水线：为当前提交推送标签 cloud-images/<提交前 12 位>（须确认）
make cloud-deploy VERSION=git-<提交前 12 位>   # 部署或更新整套环境（镜像由 make cloud-images 触发的流水线构建）
make cloud-info                   # 各组件地址与凭证位置
make cloud-dev                    # 开发模式：bff / web 换成工作区代码，保存后几秒生效；Ctrl+C 恢复稳定版本
make cloud-dev-reset              # 开发模式异常退出（如开发机重建）后恢复稳定版本
make cloud-lint / cloud-test / cloud-e2e   # 在集群内对当前工作区运行检查与测试
make cloud-unit                   # 云端脚本的 bash 单元测试（开发机上直接运行）
make cloud-build TARGET=bff|web|all        # 在集群内构建并部署（成为稳定版本）
make cloud-seed / cloud-mock-data           # 数据初始化 / 重建模拟数据（后者须确认）
make cloud-dev-metadata / cloud-dev-metadata-remove   # 导入 / 删除 006 开发态元数据（cloud-e2e 的资产搜索场景需要）
make cloud-stop / cloud-start / cloud-status   # 停止并释放弹性池 / 恢复 / 查看状态
make cloud-uninstall              # 卸载（须确认，删除全部数据）
```

## 目录

| 目录 | 内容 |
| --- | --- |
| `apps/web` | 织境 Web（React） |
| `services/bff` | 织境 Web 的后端（BFF） |
| `packages/py-core` | 公共库 `contexture-core`（鉴权、追踪、错误、MCP、本体） |
| `packages/ts-api` | 前端 API 客户端（由契约生成） |
| `contracts/` | 接口契约（OpenAPI、MCP 工具、JSON Schema、OTel 属性） |
| `deploy/` | 部署：`helmfile.yaml.gotmpl`、各开源组件（`components/`）、自建服务 Chart（`charts/`）、kind、离线包 |
| `third_party/` | 织境维护的上游仓库（OpenMetadata、Omnigent）与补丁登记 |
| `tools/` | 部署、示例数据、组件 / 补丁 / 许可检查脚本 |
| `tests/` | 端到端测试与共用测试支持代码 |


004 Web 外壳实现及验证入口：`http://localhost:8080/home`，Web 准入角色为 admin / ai-engineer。
导航包含新建对话、首页、资产搜索和 Agent 工作台；后续业务显示尚未开放，不展示假统计。
退出只结束织境会话，不调用 IdP logout。旧设备回归地址为 `/objects/equipment`。
开发组件示例和新增页面接入见 [Web 说明](apps/web/README.md)；004 完成状态以
[验收记录](specs/004-web-shell/acceptance.md) 为准，自动验证不代替负责人手动验收。

```bash
pnpm --filter @contexture/web test:coverage
pnpm --filter @contexture/ui test:coverage
make coverage-check                 # 先运行 make test 与上述覆盖率命令；默认比较 HEAD，含未跟踪新源码
make e2e KUBE_CONTEXT=kind-contexture # 临时 kubeconfig 隔离上下文；只读集群回归 → 8080 生产组 → 5173 开发组
```

003 的双规模重建测试单独执行 `make e2e-mock-data`；此命令会重建模拟 MES / QMS / mock_dw，004 回归不要运行。

2026-11-03：004 已经产品负责人验收通过并关闭，见 [验收记录](specs/004-web-shell/acceptance.md)。
2026-11-08：005 源系统元数据采集已经产品负责人验收通过并关闭，见 [验收记录](specs/005-source-metadata-ingestion/acceptance.md)。
2026-11-10：006 资产搜索与摘要已经产品负责人验收通过并关闭，见 [验收记录](specs/006-asset-search-summary/acceptance.md)。
下一项为 007 Agent 工作台与页面助手；后续按 008 推进。
