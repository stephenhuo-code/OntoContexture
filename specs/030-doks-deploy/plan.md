# Implementation Plan: DOKS 云端开发与部署环境

**Branch**: `030-doks-deploy` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/030-doks-deploy/spec.md`

**Note**: 开发机无 Python 3，Spec Kit 的 `setup-plan.sh` 无法运行（报 “Python 3 is required to honor the extension registry”）；本文件按 `.specify/templates/plan-template.md` 手工创建，
未执行 agent context 更新脚本。

## Summary

在开发机 devbox-0 所在的 DOKS 集群上建立**一套**云端织境环境，兼作开发环境。做法是复用现有 helmfile 与组件 Chart，新增 helmfile `cloud` 环境与各组件的 `values/cloud.yaml`，
本地 `local` / `lite` 的渲染结果保持不变（以渲染对比验证）。入口用 Envoy Gateway + DO 负载均衡器 + cert-manager（Let's Encrypt HTTP-01）；Keycloak 改为集群内自带；
自建镜像由手动触发的 GitHub Actions 推送到 DOCR。开发者只在开发机运行轻量客户端：
- `devspace`：开发模式下替换 bff / web 并同步源码；
- `buildctl`：连接集群内的 BuildKit 构建镜像；
- `kubectl exec`：在集群内一次性的工具箱 Pod（带 DinD 边车）里运行 lint、测试、e2e。

全部云端操作以 `make cloud-*` 命令提供，与本地命令互不越界。启停脚本按依赖顺序缩容 / 恢复工作负载，并等待弹性池缩到 0。决策依据见 [research.md](research.md)。

## Technical Context

**Language/Version**: Bash（`tools/cloud/*.sh`，开发机无 Python）；Helm 模板 / helmfile gotmpl；YAML（DevSpace、GitHub Actions）；Dockerfile；工具箱内 Python 3.12 / Node 22 运行现有测试

**Primary Dependencies**: helmfile + Helm（现有部署）、Envoy Gateway v1.9.2（现有）、cert-manager v1.21.x、BuildKit v0.34.x、DevSpace v6.3.x、kubectl、doctl、jq；DOKS、DOCR、DO 负载均衡器、GitHub Actions

**Storage**: DO 块存储（`do-block-storage`，RWO）承载现有有状态组件；环境状态记录在集群 ConfigMap `contexture-cloud-state`（data-model.md），不新增数据库

**Testing**:
- **bash 单元测试**（`tools/cloud/tests/`，自带的纯 bash 运行器）：覆盖配置校验、标签计算、状态机、启停顺序。
- **bash 行覆盖率**：用 kcov 统计，输出 cobertura 格式；`tools/coverage_gate.py` 新增 `--cobertura` 输入，纳入“新增与修改代码 ≥ 80%”门禁（宪法 I）。
  覆盖率在工具箱镜像与 CI 中统计，开发机不安装 kcov。kcov 为 GPL-2.0，只作开发测试工具，不进入交付物，按 `tools/license-allowlist.yaml` 的例外登记（ADR-0014）。
- **渲染对比测试**（`helmfile template`）：local / lite 不变；cloud 中无本地地址与 DO 专用值泄漏。
- **云端验证测试**，分两类：
  - 开发机运行的 bash 验证测试 `tests/cloud/*.sh`：部署、访问、开发模式、启停、卸载；
  - 工具箱中运行的 pytest `-m cluster` 测试 `tests/cloud/test_cloud_env.py`：环境内状态检查。
- 现有 `make test` / `make e2e` 在工具箱中运行。

**Target Platform**: DOKS v1.37（sfo2），弹性池 4 核 8 GB × 0–6；开发机 devbox-0（约 1.5 核 / 2 GiB，无 Docker）

**Project Type**: 部署与开发工具（基础设施），无新服务、无新接口

**Performance Goals**: 首次部署 ≤ 60 分钟、重复部署 ≤ 20 分钟（SC-001）；开发模式同步 ≤ 10 秒（SC-002）；lint / 单元测试 ≤ 10 分钟、集群内构建 ≤ 10 分钟（SC-004）；停止 ≤ 20 分钟、启动 ≤ 30 分钟（SC-011/012）

**Constraints**: 本地 kind 部署行为不变（SC-007）；不修改 DOKS 托管的 Gateway API CRD；开发机内存 ≤ 2 GiB；织境负载只在弹性池；凭证不入库；
开发机上需要保留的东西只放在主目录持久卷（工具、配置、日志、DevSpace 状态），devbox-0 重建后命令可直接继续，中断的命令可再次执行收敛（research R18）；
脚本与通用模板只用标准 Kubernetes API 与开源组件，DO 专用值（节点池标签、负载均衡器注解、存储类、镜像仓库）全部来自配置，便于后续 029 或其他 Kubernetes 复用（research R19）

**Scale/Scope**: 1 套环境、1 名开发者；约 20 个 Helm release；`make cloud-*` 命令见 [contracts/cloud-commands.md](contracts/cloud-commands.md)（共 16 个）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 条款 | 结论 | 依据 |
| --- | --- | --- |
| I 测试驱动 | PASS | 脚本逻辑先写 bash 单元测试，用 kcov 统计行覆盖率并纳入 80% 门禁；Chart 参数化先写渲染对比测试（local / lite 渲染前后一致，cloud 渲染断言）；集群行为写 `-m cluster` 验证测试；测试先于实现提交。集成测试在工具箱中用 DinD 运行，依赖仍为真实容器 |
| II 微服务与契约优先 | PASS | 不新增服务、不改接口。命令行与配置文件的约定先写成 [contracts/](contracts/) |
| III 开源优先与许可 | PASS | 新增 cert-manager、BuildKit、DevSpace，均为 Apache-2.0，见下方清单；cert-manager、BuildKit、CI 工具箱按 001 的组件目录登记 `component.yaml`，纳入 `make components-check` 与许可检查；`cloud-images` 流水线复用 `ci.yml` 的 SBOM、许可与漏洞扫描：许可不通过、或自建镜像（bff、web）有可修复的 Critical 漏洞则不推送；OpenMetadata 第三方镜像的漏洞结果留档告警、不阻断（与 `ci.yml` 只门禁自建镜像一致，2026-11-11，待负责人确认，见 research R9 实施记录）。kcov（GPL-2.0）只用于开发测试、不进入交付物，按许可白名单的例外登记（ADR-0014）。不引入 BUSL / AGPL 工具（不用 Terraform） |
| IV 最小权限与审计 | PASS（附风险） | 凭证只放在 `.env.cloud` 与集群 Secret 中；DOCR 拉取用只读令牌；工具箱 ServiceAccount 只有 `contexture` namespace 内的受限权限。测试用户密码同用户名、组件界面对公网开放，是负责人知情决定，写入 acceptance 已知限制 |
| V 可观测性 | PASS | 沿用现有 OTel Collector / Jaeger / Langfuse；入口追踪继续由 Envoy Gateway 提供 |
| VI 以服务集成、定制分级 | PASS | 全部是配置：Helm values、helmfile 环境、Dockerfile 新增非末尾阶段。不打补丁，不修改上游源码 |
| VII 数据模型复用 | PASS | 不新增业务实体。环境状态只是一个部署元数据 ConfigMap，不属于产品数据模型（data-model.md） |
| 部署约束：阿里云测试环境 | **偏离**（见 Complexity Tracking） | 宪法只规定阿里云 ACK / ACR，且要求测试环境由流水线基于已合并提交部署；本特性在 DOKS 上建开发 / 测试 / 演示环境，镜像可由任意分支手动构建，开发模式运行未提交代码 |
| 部署约束：Phase 1 单租户、测试环境不放客户数据 | PASS | 单租户，租户常量沿用本地；spec 规定只放模拟数据 |
| 开发流程：原型先行 | N/A | 无用户界面 |
| 开发流程：acceptance.md | PASS | tasks 最后阶段编写，包含公网暴露风险、Airflow 补跑（R13）等已知限制 |

### 开源服务与组件清单（宪法 III，本特性新增或改变用法的部分）

| 组件 | 版本 | 许可 | 用途 | 部署单元 | 可替换方案 |
| --- | --- | --- | --- | --- | --- |
| cert-manager | v1.21.x（实施时锁定） | Apache-2.0 | Let's Encrypt 证书签发与续期 | `cert-manager` namespace（仅云端） | 手工证书、DO LB 证书 |
| BuildKit（buildkitd / buildctl） | v0.34.x | Apache-2.0 | 集群内构建 bff / web / 开发 / 工具箱镜像 | `contexture-build` namespace；开发机客户端 | Kaniko（已归档）、流水线构建 |
| DevSpace | v6.3.x | Apache-2.0 | 开发模式替换 Pod 与文件同步 | 开发机客户端 | Skaffold、Tilt |
| docker:dind | 实施时锁定 | Apache-2.0（Moby） | 工具箱中为 Testcontainers 提供 Docker API | `contexture-ci` 工具箱边车 | 改测试为连接集群组件 |
| kcov | 实施时锁定 | GPL-2.0（许可白名单例外，仅开发测试） | bash 行覆盖率 | 工具箱镜像、CI，不进入交付物 | bashcov（Ruby，需另装运行时） |
| Keycloak（自带模式） | 26.8.0（现有锁定） | Apache-2.0 | 云端身份 | `keycloak` release | 外部 Keycloak |
| Envoy Gateway | v1.9.2（现有锁定） | Apache-2.0 | 入口，云端改为 LoadBalancer | `envoy-gateway` | Cilium Gateway（R2 回退方案） |
| helm / helmfile / kubectl / doctl | 见 R15 | Apache-2.0 / MIT / Apache-2.0 / Apache-2.0 | 开发机部署工具 | 开发机 | — |
| DigitalOcean DOKS / DOCR / LB | 托管服务 | 商业服务 | 集群、镜像仓库、负载均衡 | — | 阿里云 ACK / ACR（029） |

## Project Structure

### Documentation (this feature)

```text
specs/030-doks-deploy/
├── spec.md
├── plan.md              # 本文件
├── research.md          # Phase 0：R1–R17
├── data-model.md        # Phase 1：环境状态与配置
├── quickstart.md        # Phase 1：从零到可用的验证步骤
├── contracts/
│   ├── cloud-commands.md   # make cloud-* 命令契约
│   └── cloud-config.md     # .env.cloud 与 helmfile cloud 环境参数契约
├── checklists/requirements.md
└── tasks.md             # $speckit-tasks 生成
```

### Source Code (repository root)

```text
Makefile                                  # 新增 cloud-* 目标；本地目标不变（lint/test 缺工具时提示）
.env.cloud.example                        # 云端配置模板（入库，无真实值）
.gitignore                                # 新增 .devspace/
.github/workflows/cloud-images.yml        # 手动触发的镜像流水线（R9）
deploy/
├── helmfile.yaml.gotmpl                  # 新增 cloud 环境；cert-manager、buildkit 等 release 仅 cloud 安装
├── cloud/
│   └── devspace.yaml                     # 开发模式（R11）
├── components/cert-manager/              # 新组件：component.yaml、values、Issuer / Certificate 模板、冒烟测试（R4）
├── components/buildkit/                  # 新组件：component.yaml、buildkitd Deployment + PVC、冒烟测试（R10）
├── components/ci-toolbox/                # 新组件：component.yaml（工具箱镜像、docker:dind、kcov 例外）、Dockerfile、namespace / RBAC / 缓存 PVC（R12）
├── components/<组件>/values/cloud.yaml(.gotmpl)   # 每个组件的云端参数（R3、R5–R8）
├── components/envoy-gateway/config/      # EnvoyProxy 服务类型、HTTPS 监听器、重定向参数化（本地默认不变）
├── components/smoke-lib.sh               # 可选 CTX_NODE_SELECTOR
└── charts/{bff,web}/                     # 可选 nodeSelector / imagePullSecrets；web 支持开发服务器参数
services/bff/Dockerfile, apps/web/Dockerfile   # 新增非末尾 dev 阶段
apps/web/vite.config.ts                   # HMR / allowedHosts 读环境变量（默认不变）
tests/e2e/playwright*.config.ts           # baseURL 读环境变量（默认不变）
tools/cloud/
├── common.sh                             # 读取并校验 .env.cloud、固定 --context/--namespace（FR-001a/002/004）
├── tools.lock / install-tools.sh         # make cloud-tools（R15）
├── secrets.sh                            # 生成集群 Secret（不覆盖已有）（R14）
├── deploy.sh / uninstall.sh              # cloud-deploy / cloud-uninstall
├── lifecycle.sh                          # cloud-stop / cloud-start / cloud-status（R13）
├── build.sh                              # cloud-build（R10）
├── dev.sh                                # cloud-dev / cloud-dev-reset（R11）
├── toolbox.sh                            # cloud-lint / test / e2e / seed / mock-data（R12）
├── info.sh                               # cloud-info
└── tests/                                # bash 单元测试与渲染对比测试
tests/cloud/                              # -m cluster 的云端验证测试
docs/adr/0014-云端开发环境.md              # 工具选型 ADR（R17）
```

**Structure Decision**：新增脚本放在 `tools/cloud/`；新增开源组件按 001 的组件目录规范放在 `deploy/components/<组件>/`（含 `component.yaml`）；组件差异只放在各组件的 `values/cloud.yaml`。
`tools/coverage_gate.py` 新增 `--cobertura` 输入，`tools/license-allowlist.yaml` 新增 kcov 的例外。现有共享文件只做“新增可选参数、默认值等于现状”的修改，
用 local / lite 渲染对比测试守住不变（SC-007）。

## 实施阶段与闸门

| 阶段 | 内容 | 完成标志（闸门） |
| --- | --- | --- |
| A 集群打底与实测 | `cloud-tools`；`.env.cloud`；Envoy Gateway + LB + cert-manager 在集群上跑通；逐项验证 R2、R3、R5、R6、R11、R13 的【实测待验】项；BuildKit 与工具箱镜像；**宪法修订获批** | Gateway `Programmed`，staging 证书签发成功；各实测结论回写 research.md；R13 Airflow 补跑问题向负责人确认；宪法修订在首次云端部署前获负责人批准 |
| B 云端部署 | 渲染对比测试（红）→ 各组件 cloud 参数、Keycloak 自带、DOCR 拉取、节点固定（DO 专用值参数化，R19）→ `cloud-deploy` / `cloud-info` / `cloud-uninstall` | 全部冒烟测试通过；local / lite 渲染不变；脚本与通用模板中无 DO 专用值；US1、US4、US7 验收场景通过 |
| C 镜像 | `cloud-images.yml`；BuildKit；`cloud-build` | 流水线产出 5 个镜像；集群内构建并更新环境 ≤ 10 分钟（US5） |
| D 开发与测试 | 工具箱镜像与 `cloud-lint/test/e2e/seed/mock-data`；DevSpace 开发模式与恢复 | US2、US3 验收场景通过；现有测试在工具箱中全部通过 |
| E 启停 | `cloud-stop` / `cloud-start` / `cloud-status` | US6 验收场景通过；弹性池缩到 0，启动后数据完整 |
| F 收尾 | ADR-0014 定稿、开发计划进度；acceptance.md | 自动化验证全部通过；负责人手动验收 |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| 在 DOKS（非阿里云 ACK / ACR）上建立测试 / 演示环境 | 负责人的开发机就在 DOKS 集群中，无 Docker、资源小，无法运行 kind；需要可公网访问的开发与演示环境（负责人 2026-11-10 决定） | 等待 029 阿里云测试环境：排在 2027-04，无法支撑当前开发；本地 kind：开发机条件不允许。处置：A 阶段提交宪法 MINOR 修订，在首次云端部署前取得负责人批准，增加“自有云端开发环境（DOKS）”条款并写明其不承载客户数据；029 仍按原计划 |
| 测试环境不由“流水线基于已合并提交”部署：镜像可由任意分支手动构建，开发模式运行未提交代码 | 这是开发环境的本质需求：改代码后几秒内生效，不经 git（spec US2、US5） | 只部署已合并提交：每轮修改都要走 PR 合并，开发不可行。处置：同一宪法修订中写明该环境属于开发环境，状态命令标明版本来源与是否含未提交改动（FR-036），演示与验收前用流水线版本重新部署 |
