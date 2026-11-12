# Tasks: DOKS 云端开发与部署环境

**Input**: Design documents from `specs/030-doks-deploy/`
**Prerequisites**: plan.md、spec.md、research.md（R1–R19、R17a）、data-model.md、contracts/cloud-commands.md、contracts/cloud-config.md、quickstart.md

**Tests**: 宪法原则 I 要求测试先行。每个故事都先写测试并确认失败（红），再实现（绿）。测试分四类：
- **渲染对比测试** `tools/cloud/tests/render-compare.sh`：`helmfile -e local|lite template` 与基线逐字节一致；`-e cloud` 的渲染结果中不出现本地地址；通用模板和脚本中不出现 DO 专用值。
- **bash 单元测试** `tools/cloud/tests/test_*.sh`：由 `tools/cloud/tests/run.sh` 执行，开发机上可直接运行。
- **bash 行覆盖率**：在工具箱与 CI 中用 kcov 统计，输出 cobertura，由 `tools/coverage_gate.py --cobertura` 纳入 ≥ 80% 门禁（R17a）。
- **云端验证测试**：开发机上运行的 bash 测试 `tests/cloud/test_*.sh`（部署、访问、开发模式、启停、卸载），以及在工具箱中运行的 `tests/cloud/test_cloud_env.py`（`-m cluster`，环境内状态检查）。

**Organization**: 按 plan 的阶段组织：
- A：Phase 1–2；
- B：US1、US4、US7；
- C：US5；
- D：US3、US2；
- E：US6；
- F：收尾。

**执行顺序按依赖，不按优先级**：US2、US3 是 P1，但它们依赖 US1 的环境和 US5 的构建能力，所以排在 US4、US5 之后。

## Format: `[ID] [P?] [Story] Description`

- **[P]**：可并行（不同文件，且不依赖未完成的任务）
- **[Story]**：对应 spec.md 的用户故事（US1–US7）；每个任务都标出 FR 或 research 编号
- 云端命令的约定见 [contracts/cloud-commands.md](contracts/cloud-commands.md)

---

## Phase 1: Setup（阶段 A：开发机工具、配置与测试设施）

- [X] T001 编写 `tools/cloud/tests/run.sh`（纯 bash 测试运行器：发现 `test_*.sh` 文件，每个 `test_` 函数在子 shell 中运行，汇总结果并设置退出码；设置 `CTX_KCOV` 时，在 kcov 下运行并把结果合并输出到 `coverage/bash/cobertura.xml`）；在 `Makefile` 新增 `cloud-unit` 目标（R17a）
- [X] T002 [P] 在 `tools/tests/test_coverage_gate.py` 编写失败测试：`--cobertura <文件>` 能解析 kcov 输出的 cobertura XML，并按 `--base` 的差异统计新增和修改行的覆盖率，与 `--python`、`--lcov` 合并后一起参与 80% 门禁（宪法 I、R17a）
- [X] T003 在 `tools/coverage_gate.py` 实现 `--cobertura` 输入，使 T002 通过（R17a）
- [X] T004 [P] 编写失败测试 `tools/cloud/tests/test_tools_lock.sh`：`tools/cloud/tools.lock` 每行为“名称 版本 许可 URL SHA256”，至少包含 kubectl、helm、helmfile、doctl、devspace、buildctl、jq，且版本发布早于锁定日期 14 天（FR-031、R15）
- [X] T005 [P] 编写失败测试 `tools/cloud/tests/test_install_tools.sh`：用本地伪造的下载源验证安装到 `$HOME/.local/bin`；SHA256 不符时拒绝安装；已安装且版本一致时跳过；缺少 git / curl / openssl / tar 时以退出码 2 报错（FR-031、R18）
- [X] T006 创建 `tools/cloud/tools.lock` 与 `tools/cloud/install-tools.sh`，在 `Makefile` 新增 `cloud-tools` 目标，使 T004、T005 通过（FR-031）
- [X] T007 在开发机执行 `make cloud-tools`，把各工具的版本和运行时内存占用（开发机限额 2 GiB）记录到 `specs/030-doks-deploy/research.md` R15（FR-014、FR-031）
- [X] T008 [P] 编写失败测试 `tools/cloud/tests/test_config.sh`：覆盖 contracts/cloud-config.md 中每个键的校验规则（缺必填键、kubeconfig 权限不是 600、上下文不存在、域名为 `localhost` / `*.nip.io`、`CTX_CLOUD_ACME_SERVER` 不是 `staging|production`，都以退出码 2 退出；输出中不回显令牌值）（FR-004、FR-005）
- [X] T009 [P] 编写失败测试 `tools/cloud/tests/test_context_pinning.sh`：用 kubectl 桩函数断言 `ctx_kubectl` / `ctx_helm` / `ctx_helmfile` 始终带 `--kubeconfig`、`--context`、`--namespace`，并且从不调用 `kubectl config use-context`（FR-001a、FR-002）
- [X] T010 创建 `tools/cloud/common.sh`：读取并校验 `.env.cloud`；提供固定上下文的命令封装；确认函数（交互式输入 `yes`，或设置 `CONFIRM=yes`，否则退出码 3）；退出码常量；日志写到 `~/.cache/contexture/logs/`（R18）。使 T008、T009 通过
- [X] T011 [P] 创建 `.env.cloud.example`（列出全部键，只填占位值并加注释）；在 `.gitignore` 新增 `.devspace/` 与 `coverage/bash/`；确认 `.env.cloud` 已被 `.env.*` 规则忽略（FR-005、R18）
- [X] T012 [P] 在 `.github/workflows/ci.yml` 新增 `cloud-scripts` 任务：安装 kcov、jq，以及 `tools/cloud/tools.lock` 中锁定的 helm 和 helmfile；运行 `CTX_KCOV=1 make cloud-unit` 和 `tools/cloud/tests/render-compare.sh`；对 `.github/workflows/*.yml` 运行 actionlint；把 `coverage/bash/cobertura.xml` 传给 `coverage-check`（宪法 I、CI 门禁）
- [X] T013 [P] 在 `tools/license-allowlist.yaml` 的 `exceptions` 中登记 kcov（`license: GPL-2.0`，`component: ci-toolbox`，`scope: 仅 CI 工具箱与 CI 运行器中的 bash 覆盖率统计，不进入交付物`，`adr: docs/adr/0014-云端开发环境.md`）；同时起草 `docs/adr/0014-云端开发环境.md` 的框架（背景、决定、许可例外）（R17a）

---

## Phase 2: Foundational（阶段 A：渲染基线、集群实测、公共基础、宪法修订）

**⚠️ CRITICAL**: 本阶段完成前不开始任何用户故事。

### 渲染基线（必须在修改任何共享文件之前完成）

- [X] T014 编写 `tools/cloud/tests/render-compare.sh`：
  - 对 `local`、`lite` 执行 `helmfile -f deploy/helmfile.yaml.gotmpl -e <env> template`（排除 `group=mock-sources`），与 `tools/cloud/tests/baseline/{local,lite}.yaml` 逐字节比较；
  - 对 `cloud` 环境断言渲染结果中不含 `localhost`、`127.0.0.1.nip.io`、`ctx-trusted-ca`、`NodePort`；
  - 对 `tools/cloud/`、`deploy/cloud/` 以及各组件的 `values/base.yaml` 断言不含 `digitalocean`、`do-block-storage`、`doks.`（`values/cloud.yaml` 与 `.env.cloud.example` 除外）。

  （SC-007、FR-021、R19）
- [X] T015 从 `main@104c55f` 的渲染结果生成基线 `tools/cloud/tests/baseline/local.yaml`、`lite.yaml` 并提交。此时本地部分通过，云端部分因为还没有 `cloud` 环境而失败（红）（SC-007）

### 集群实测（结论回写 research.md）

- [X] T016 在 `deploy/helmfile.yaml.gotmpl` 新增 `cloud` 环境骨架：值 `domain`、`nodeLabel`、`nodePool`、`storageClass`、`registry`、`acmeServer`、`acmeEmail` 来自 `.env.cloud`；暂时只启用 `envoy-gateway` 与 `gateway` 两个 release。T014 的本地部分必须仍然通过（FR-001、R7、R19）
- [X] T017 实测 R2：在集群中按 `cloud` 环境安装 Envoy Gateway v1.9.2，确认 Helm 跳过了已存在的 Gateway API CRD，没有触发 `doks-gateway-api-crd-protection`，且 Gateway `contexture` 状态为 `Programmed`。不兼容时按 R2 的回退方案处理；结论写入 `specs/030-doks-deploy/research.md` R2
- [X] T018 把 `deploy/components/envoy-gateway/config/`（`values.yaml`、`templates/gateway.yaml`）参数化：
  - `envoyService.type`（默认 `NodePort`、`nodePort: 30080`）
  - `loadBalancer.annotations`
  - `https` 监听器及证书引用
  - HTTP→HTTPS 重定向 `HTTPRoute`
  - `nodeSelector`、`tenantId`

  新建 `deploy/components/envoy-gateway/values/cloud.yaml`（LoadBalancer，加 DO 注解参数块）。T014 的本地部分必须仍然通过（FR-019、R3、R19）
- [X] T019 实测 R3：部署一个临时 echo 后端，确认 LB 拿到公网 IP；把 Envoy 缩为 0 后访问 LB，记录响应码和耗时，写入 research.md R3，并把实测到的响应（如 503）回写到 `specs/030-doks-deploy/spec.md` 的 FR-037（FR-037）
- [X] T020 [P] 新建组件 `deploy/components/cert-manager/`：
  - `component.yaml`：版本 v1.21.x、Apache-2.0、镜像清单、冒烟测试；
  - `values/cloud.yaml`：开启 Gateway API 支持，加 `nodeSelector`；
  - `config/`：staging 和 production 两个 `ClusterIssuer`；一张 `Certificate`，包含 `<domain>` 和 R3 列出的全部子域名；
  - `tests/smoke.sh`：Certificate 为 Ready。

  在 helmfile 中只为 `cloud` 环境安装；`make components-check` 通过（FR-019、R4、R17a）
- [X] T021 实测 R4、R5：用 staging 签发器完成 HTTP-01 签发；在集群内临时 Pod 中 `curl https://<domain>`，验证经 LB IP 的集群内访问可达。结论写入 research.md R4、R5（FR-019、FR-021）
- [X] T022 实测 R6：以 `cloud` 环境安装 Airflow（Pod 亲和加 `nodeSelector`），触发一次 KubernetesExecutor 任务，确认任务 Pod 与调度器在同一节点，且 DAG 卷可以挂载。结论写入 research.md R6；如果全局 `affinity` 对任务 Pod 不生效，就在 `deploy/components/airflow/values/cloud.yaml.gotmpl` 的 `podTemplate` 里补上（FR-025、R6）
- [X] T023 实测 R13 的补跑问题：准备一个每 10 分钟调度一次、`catchup=False` 的测试 DAG，把调度器缩为 0，跨过两个调度点后再恢复，记录 Airflow 是否为最近一个区间创建了运行。结论写入 research.md R13，并**请负责人确认**：接受补跑（同步修订 spec 的边界情况），还是启动时跳过（见 T086）
- [X] T024 实测 R11：在临时 namespace 中，用 DevSpace v6.3 的 replace-pods 替换一个由 helm 部署的 Deployment。测量文件同步延迟（目标 ≤ 10 秒）；验证 `devspace reset pods` 能恢复原 Deployment；验证替换期间执行 `helm upgrade` 会有什么影响；验证同步连接中断再恢复后，改动会被补齐。结论写入 research.md R11（FR-011、FR-012）

### 公共基础

- [X] T025 [P] 编写失败测试 `tools/cloud/tests/test_secrets.sh`：用 kubectl 桩函数断言：
  - 只创建不存在的 Secret，已存在的不覆盖；覆盖 contracts/cloud-config.md 列出的全部 Secret 名称和键，含 `keycloak-admin`、`pg-keycloak`、`docr-pull`；
  - `docr-pull` 每次按配置更新；
  - 不创建 `ctx-trusted-ca`；
  - Fernet 密钥是 32 字节的 urlsafe base64。

  （FR-003、FR-010、R14）
- [X] T026 实现 `tools/cloud/secrets.sh`（bash + openssl），使 T025 通过（FR-003、FR-010、R14）
- [X] T027 [P] 编写失败测试 `tools/cloud/tests/test_image_tags.sh`：覆盖 data-model.md 第 4 节的标签规则：
  - 流水线构建为 `git-<12位>`；
  - 工作区干净时为 `ws-<12位>`；
  - 有未提交改动时为 `ws-<12位>-<8位>`，同样的工作区得到同样的标签；
  - `dev-` 和 `toolbox-` 标签只随锁文件变化。

  （FR-022、FR-023）
- [X] T028 [P] 编写失败测试 `tools/cloud/tests/test_state.sh`：覆盖 `contexture-cloud-state` 中 `stableVersion.*`、`devMode.*`、`lifecycle.*` 的读写，以及“`lifecycle.state` 与实际副本数共同判定 运行中 / 已停止 / 部分运行”的规则（data-model.md 第 2 节，FR-036）
- [X] T029 实现 `tools/cloud/lib/tags.sh` 与 `tools/cloud/lib/state.sh`，使 T027、T028 通过
- [X] T030 [P] 新建组件 `deploy/components/buildkit/`：
  - `component.yaml`：v0.34.x、Apache-2.0、镜像清单；
  - `chart/`：`contexture-build` namespace；特权模式的 `buildkitd` Deployment，默认 0 副本，带 `nodeSelector`；20Gi 缓存 PVC，使用 `storageClass`；推送凭证 `docr-push`；
  - `tests/smoke.sh`。

  在 helmfile 中只为 `cloud` 环境安装；`make components-check` 通过（FR-022、R10、R17a）
- [X] T031 实现 `tools/cloud/lib/buildkit.sh`：启动前先清理残留副本 → 扩为 1 副本并等待就绪 → 用 `buildctl --addr kube-pod://…` 按指定的 Dockerfile、目标阶段和标签构建并推送 → 缩回 0（R10、R18）
- [X] T032 [P] 新建组件 `deploy/components/ci-toolbox/`：
  - `component.yaml`：工具箱镜像、`docker:dind`、kcov 例外；
  - `Dockerfile`：Python 3.12 + uv、Node 22 + pnpm、Playwright 浏览器依赖、kubectl、helm、kcov，版本与仓库的锁定版本一致；
  - `chart/`：`contexture-ci` namespace；`toolbox-cache` PVC；只能读写 `contexture` 和 `mock-sources` 的 ServiceAccount 与 Role；Secret `toolbox-env`，以环境变量形式提供 seed、e2e、mockfactory 需要的凭证（Keycloak 管理员、模型服务、测试用户），由 `secrets.sh` 生成。

  （FR-015、FR-017、R12、R17a）
- [X] T033 用 `lib/buildkit.sh` 构建工具箱镜像（标签 `toolbox-<摘要>`），推送到 DOCR，记录构建耗时（R12）
- [X] T034 [P] 编写失败测试 `tools/cloud/tests/test_toolbox.sh`：用 kubectl 桩函数断言：
  - 上传的文件清单等于 `git ls-files -co --exclude-standard`，且不包含 `.env.*`；
  - 凭证只通过 Secret `toolbox-env` 的环境变量注入；
  - 命令的退出码被透传；
  - 收到 SIGINT 时删除工具箱 Pod；
  - 启动前先清理同名残留 Pod；
  - 设置 `CTX_KCOV` 时在 kcov 下运行 `cloud-unit`，并把 cobertura 结果取回本地。

  （FR-015、FR-016、R12、R18）
- [X] T035 实现 `tools/cloud/lib/toolbox.sh`：创建主容器加 `docker:dind` 边车的 Pod，上传工作区，用 `kubectl exec` 执行命令并透传退出码，通过 `trap` 清理。使 T034 通过（FR-015～FR-017）
- [X] T036 在 `Makefile` 的 `lint`、`test` 目标前加入检查：找不到 `uv` 时，提示改用 `make cloud-lint` / `make cloud-test` 并以退出码 2 结束；有 `uv` 时行为不变（FR-001a）
- [X] T037 新建 `.github/workflows/cloud-images.yml`：
  - 只能通过 `workflow_dispatch` 手动触发，输入为分支或提交；
  - 检出时包含 `third_party/openmetadata/src` 子仓库；
  - 用 `DIGITALOCEAN_REGISTRY_TOKEN` 登录 DOCR；
  - 构建 bff、web，打 `git-<sha>` 标签；
  - OM 三个镜像：仓库里已有同版本就跳过，否则设置 `CTX_REGISTRY` 后调用 `third_party/openmetadata/build/build.sh`；
  - 对全部新构建的镜像复用 `ci.yml` 中 syft、grype、trivy 的 SBOM、许可与漏洞扫描步骤，扫描不通过就不推送；
  - 全部成功后统一推送。

  （FR-023、R9、宪法 III）
- [X] T037a [P] 编写 `tools/cloud/tests/test_images.sh`（先失败）：`make cloud-images` 在工作区有未提交改动或处于游离 HEAD 时以退出码 2 拒绝；未确认时退出码 3 且不推送；确认后推送当前分支与标签 `cloud-images/<提交前 12 位>`；远端已有该标签时提示已触发过、不重复推送；流水线文件含 `cloud-images/*` 标签触发且不含分支推送触发（FR-023，2026-11-11 澄清）
- [X] T037b 实现 `tools/cloud/images.sh` 与 `make cloud-images`，并给 `cloud-images.yml` 增加推送 `cloud-images/*` 标签的触发（检出 `inputs.ref`，为空时取标签指向的提交），使 T037a 通过；同步 contract、quickstart、research R9（FR-023）
- [X] T038 手动触发一次 `cloud-images` 流水线，确认 5 个镜像推送到 DOCR、SBOM 已上传，记录耗时（SC-008）
- [X] T039 提交宪法 MINOR 修订：在 `.specify/memory/constitution.md` 的“部署约束”中新增“自有云端开发环境（DOKS）”条款，内容包括：只放模拟数据、不承载客户数据；允许手动构建任意分支、允许运行开发模式；演示和验收前要用流水线构建的版本重新部署。同时升级版本号并写明修订原因。**必须在 T052 首次云端部署之前取得负责人批准**（plan Complexity Tracking、R17） ——**2026-11-11 负责人 @stephenhuo-code 批准 v2.3.0**

**Checkpoint**：R2–R6、R11、R13 的实测结论已回写；入口、证书、节点固定、密钥、构建、工具箱都已可用；本地渲染不变；宪法修订已获批准。

---

## Phase 3: User Story 1 - 运维者一条命令部署云端环境 (Priority: P1) 🎯 MVP（阶段 B）

**Goal**：`make cloud-deploy` 拉起全部平台组件（含自带 Keycloak），可重复执行。

**Independent Test**：执行 `make cloud-deploy VERSION=git-<sha>`，冒烟测试全部通过；再执行一次，数据和密码不变。

### Tests for User Story 1 ⚠️

- [X] T040 [P] [US1] 扩充 `tools/cloud/tests/render-compare.sh` 的云端断言（红）：
  - 每个 release 都带 `nodeSelector: {<nodeLabel>: <nodePool>}`；
  - 每个 PVC 都使用 `storageClass`；
  - 自建镜像都来自 `registry`，并带 `imagePullSecrets: docr-pull`；
  - Keycloak 为 `enabled: true`、`hostname: https://sso.<domain>`、`withTestUsers: true`；
  - bff 的 `publicUrl` 为 `https://<domain>`。

  （FR-006～FR-009、FR-021、FR-024、FR-027、R7、R19）
- [X] T041 [P] [US1] 编写失败测试 `tools/cloud/tests/test_deploy.sh`：
  - 缺少配置时，在执行任何修改集群的命令之前就退出（FR-004）；
  - 处于开发模式时要求确认（FR-013）；
  - 首次部署没有给 `VERSION` 时以退出码 2 退出；
  - 部署前检查发现 CNPG、Doris、Envoy Gateway、cert-manager 的 CRD 已存在且没有织境标记时，停止并报告（spec 边界情况）；
  - 等待超时时，列出处于 Pending 的 Pod 及其调度失败原因，以及处于 `ImagePullBackOff` / `ErrImagePull` 的 Pod（spec 边界情况）；
  - 部署成功后写入 `stableVersion`，`source=pipeline`（FR-024）。
- [X] T042 [P] [US1] 编写云端验证测试 `tests/cloud/test_deploy.sh`（在开发机运行）：部署后冒烟测试全部通过；第二次部署后，`pg-*`、`langfuse-*`、`om-secrets` 等 Secret 的值不变，Keycloak 中的 `user1` 仍然可以登录（US1 场景 1、2；FR-003；SC-006）

### Implementation for User Story 1

- [X] T043 [P] [US1] 新建 `deploy/components/postgresql/values/cloud.yaml`：`databases` 增加 `keycloak`，设置 `storageClass` 和 `nodeSelector`。在 `deploy/components/postgresql/config` 中加可选的 storageClass 和 nodeSelector 参数，默认为空（FR-007、FR-025）
- [X] T044 [P] [US1] 新建 `deploy/components/keycloak/values/cloud.yaml.gotmpl`：
  - 自带模式，设置 `hostname`；
  - `import.url` 指向集群内服务；
  - 使用 `keycloak-admin`；
  - `trustedCaSecret: ""`；
  - 云端的 `publicUrl` 和 `omUrl`；
  - `withTestUsers: true`；
  - `nodeSelector`。

  如果 Chart 没有 nodeSelector 参数，就新增一个，默认为空（FR-007～FR-010、R5）
- [X] T045 [P] [US1] 新建 `deploy/components/openmetadata/values/cloud.yaml.gotmpl`：
  - OIDC 地址改为 `https://sso.<domain>/realms/digital-workforce`；
  - 清空 truststore 相关的 `extraInitContainers`、`extraVolumes`、`extraVolumeMounts`；
  - `OPENMETADATA_OPTS` 中去掉 truststore 参数；
  - 镜像仓库改为 DOCR，并设置 `imagePullSecrets`；
  - `nodeSelector`。

  （FR-008、FR-021、R5）
- [X] T046 [P] [US1] 完善 `deploy/components/airflow/values/cloud.yaml.gotmpl`：亲和方案沿用 T022 的结论；织境 Airflow 镜像改为 DOCR；设置 `storageClass` 和 `nodeSelector`（FR-025、R6）
- [X] T047 [P] [US1] 为以下组件新建 `values/cloud.yaml(.gotmpl)`：opensearch、opensearch-dashboards、fuseki、doris、langfuse、mcp-toolbox、ai-gateway、jaeger、prometheus、otel-collector（均在 `deploy/components/` 下）。内容：
  - 资源以 `local` 为基线（R16）；
  - `storageClass`、`nodeSelector`；
  - AI 网关：`keycloakIssuer` 改为云端地址，`trustedCaSecret: ""`。

  另外给 Doris operator 和 CNPG operator 的 values 加 `nodeSelector`（FR-021、FR-025、FR-027）
- [X] T048 [P] [US1] 为 `deploy/charts/bff` 和 `deploy/charts/web` 新增可选参数 `nodeSelector`、`imagePullSecrets`、`route.hostnames`，默认值与现状一致；并新建 `deploy/charts/{bff,web}/values-cloud.yaml.gotmpl`，设置 `publicUrl`、`keycloakUrl`、`trustedCaSecret: ""`，镜像来自 `registry` 的 `bffTag` / `webTag`（FR-008、FR-021、FR-024）
- [X] T049 [US1] 修改 `deploy/components/smoke-lib.sh`：设置了 `CTX_NODE_SELECTOR` 时，临时 Pod 附加 `--overrides`（FR-027、R7）
- [X] T050 [US1] 在 `deploy/helmfile.yaml.gotmpl` 中为全部平台 release 启用 `cloud` 环境；cert-manager、buildkit、ci-toolbox 只在 `cloud` 环境安装。使 T040 通过，T014 本地部分仍然通过（FR-006）
- [X] T051 [US1] 实现 `tools/cloud/deploy.sh`，并在 `Makefile` 新增 `cloud-deploy` 目标，流程依次为：
  1. 校验配置；
  2. 如处于开发模式，要求确认；
  3. CRD 部署前检查；
  4. 运行 `secrets.sh`；
  5. `helmfile -e cloud sync`，排除 mock-sources；
  6. 在工具箱中运行 `tools.om_config`；
  7. 设置 `CTX_NODE_SELECTOR` 后运行全部冒烟测试，日志写到 `~/.cache/contexture/logs/`；失败时汇总 Pending 和镜像拉取的错误；
  8. 写入状态记录；
  9. 输出访问地址、LB IP 和需要配置的 DNS 记录。

  使 T041 通过（FR-002～FR-006、FR-014、FR-021、FR-024、FR-028）
- [X] T052 [US1] 在集群上执行 `make cloud-deploy`：先用 staging 签发器，验证通过后切换到 production（实测修订：staging 只验证签发流程，完整部署直接用 production，见 research R4 实施记录）。使 T042 通过，并记录首次部署和重复部署的耗时（SC-001）

**Checkpoint**：云端环境可以部署、可以重复部署，冒烟测试全部通过（MVP）。

---

## Phase 4: User Story 4 - 团队通过域名以 HTTPS 访问云端环境 (Priority: P2)（阶段 B）

**Goal**：织境 Web、Keycloak 和各组件的子域名都能通过受信任的 HTTPS 访问。

**Independent Test**：浏览器打开 `https://<domain>`，用 `user1` 登录；访问 HTTP 时跳转到 HTTPS；各子域名都能打开。

- [X] T053 [P] [US4] 编写云端验证测试 `tests/cloud/test_access.sh`：
  - 对 `<domain>` 和全部子域名执行 `curl` 校验证书链，不加 `-k`；
  - `http://` 返回 301 或 308，跳转到 `https://`；
  - 未登录访问时跳转到 `sso.<domain>`；
  - 模拟源系统的数据库端口不对外开放。

  （US4 场景 1、3、4；FR-019、FR-020）
- [X] T054 [P] [US4] 编写 `tests/cloud/test_cloud_env.py`（`-m cluster`，在工具箱中运行）：Certificate 为 Ready 且包含全部主机名；续期设置为提前 30 天（US4 场景 5）
- [X] T055 [US4] 为 OpenMetadata、Langfuse、Airflow、Jaeger、Prometheus、OpenSearch Dashboards、AI 网关管理界面和 Keycloak 在各自的 `values/cloud.yaml(.gotmpl)` 中新增按子域名的 `HTTPRoute`，主机名按 R3。AI 网关管理界面目前只监听 Pod 内地址，需要在 `deploy/components/ai-gateway/chart` 中增加一个可选的 Service，默认关闭（FR-020）
- [X] T056 [US4] 实现 `tools/cloud/info.sh`，并在 `Makefile` 新增 `cloud-info` 目标：按 `tools/ports.sh` 中的组件列表，输出各组件的云端地址、登录方式，以及凭证所在的 Secret 名和键；不输出凭证值（FR-029；US7 场景 1）
- [ ] T057 [US4] 运行 T053、T054，使其通过；在浏览器中以 `user1` 登录，并记录登录耗时（SC-005）

---

## Phase 5: User Story 7 - 云端环境可查看、可排障、可卸载 (Priority: P3)（阶段 B）

- [X] T058 [P] [US7] 编写失败测试 `tools/cloud/tests/test_uninstall.sh`：
  - 删除对象清单只包含 data-model.md 第 3 节列出的 namespace，以及织境创建的 CRD、GatewayClass、ClusterRole；
  - 清单中永远不包含 `dev`、`kube-*`，也不包含 `gateway.networking.k8s.io` 的 CRD；
  - 未确认时不调用任何删除命令。

  （FR-030）
- [X] T059 [US7] 实现 `tools/cloud/uninstall.sh`，并在 `Makefile` 新增 `cloud-uninstall` 目标，使 T058 通过（FR-030）
- [ ] T060 [US7] 编写并执行云端验证测试 `tests/cloud/test_uninstall.sh`：卸载前后其他 namespace 中的资源数量一致，devbox-0 仍在运行。之后重新执行 `make cloud-deploy` 恢复环境（SC-009） ——**负责人 2026-11-11 决定本轮跳过**（会删除全部数据并需重建约 1–1.5 小时；卸载逻辑由单元测试覆盖，未在集群实测，记入 acceptance 已知限制）

---

## Phase 6: User Story 5 - 镜像构建 (Priority: P2)（阶段 C）

- [X] T061 [P] [US5] 编写失败测试 `tools/cloud/tests/test_build.sh`：
  - `TARGET=bff|web|all` 的参数解析；
  - 不构建 OpenMetadata 相关镜像；
  - 构建失败时不更新环境、不写状态记录；
  - 构建成功时写入 `stableVersion`（`source=workspace`、`commit`、`dirty`）。

  （FR-022；US5 场景 1、5）
- [X] T062 [US5] 实现 `tools/cloud/build.sh`，并在 `Makefile` 新增 `cloud-build` 目标；支持 `--dev` 和 `--toolbox`，这两种只构建、不部署。流程：调用 `lib/buildkit.sh` 构建 → `helmfile -e cloud -l component=bff|web sync` → 写状态记录。使 T061 通过（FR-022）
- [X] T063 [US5] 执行 `make cloud-build TARGET=all`，验证 10 分钟内完成，且状态命令显示来源以及是否含未提交改动（SC-004；US5 场景 1、4）

---

## Phase 7: User Story 3 - 开发者在集群内运行检查与测试 (Priority: P1)（阶段 D）

- [X] T064 [P] [US3] 编写失败测试 `tools/cloud/tests/test_toolbox_targets.sh`：
  - 每个 `cloud-*` 命令都映射到工具箱里正确的命令；
  - `cloud-mock-data` 先列出将被重建的库（`mes`、`qms`、`mock_dw`）并要求确认；未确认时以退出码 3 退出，且不创建 Pod；
  - `cloud-seed` 和 `cloud-e2e` 不需要确认。

  （FR-015、FR-018、FR-026、FR-029）
- [X] T065 [P] [US3] 编写云端验证测试 `tests/cloud/test_toolbox_run.sh`：
  - 在临时分支中加入一个必定失败的用例，执行 `make cloud-test` 后退出码不为 0，且不残留 Pod；
  - 按 Ctrl+C 中断后，Pod 被删除。

  （US3 场景 1、2、4；FR-016）
- [X] T066 [US3] 实现 `tools/cloud/toolbox.sh`，并在 `Makefile` 新增 `cloud-lint`、`cloud-test`、`cloud-e2e`、`cloud-seed`、`cloud-mock-data` 目标。`cloud-test` 中带上 `CTX_KCOV=1 make cloud-unit`，并输出 bash 覆盖率。`cloud-mock-data` 先执行 `helmfile -e cloud -l group=mock-sources sync`，再在工具箱中运行 mockfactory。使 T064 通过（FR-015～FR-018、FR-026、FR-029）
- [X] T067 [US3] 修改以下文件，默认值保持不变：
  - `tests/e2e/playwright.config.ts`、`tests/e2e/playwright.ui.config.ts`：`baseURL` 改为读取 `CTX_E2E_BASE_URL`；
  - `testdata/deploy/{mes,qms}`、`testdata/deploy/secrets.sh`：参数化 kube 上下文和 nodeSelector。

  （FR-018、FR-026）
- [ ] T068 [US3] 依次执行 `make cloud-lint`、`make cloud-test`、`make cloud-mock-data`、`make cloud-seed`、`make cloud-e2e`，修复问题直到全部通过；使 T065 通过；记录各命令耗时（SC-004）

---

## Phase 8: User Story 2 - 开发者改代码后几秒内在云端环境看到效果 (Priority: P1)（阶段 D）

- [X] T069 [P] [US2] 编写失败测试 `tools/cloud/tests/test_dev.sh`：
  - 环境未运行或已停止时，以退出码 2 退出；
  - 进入开发模式时写入 `devMode.active=true`；
  - 收到 EXIT 或 INT 时执行 `devspace reset pods`，并写入 `devMode.active=false`；
  - 没有本地进程时，`cloud-dev-reset` 也能恢复。

  （FR-011～FR-013、R18）
- [X] T070 [P] [US2] 编写云端验证测试 `tests/cloud/test_dev_mode.sh`：
  - 修改 bff 接口的返回文案和 web 页面上的一处文字，10 秒内都在 `https://<domain>` 上生效；
  - 中断同步连接再恢复后，改动被补齐；
  - 退出后 5 分钟内恢复为稳定版本。

  （US2 场景 2、5；SC-002；spec 边界情况“网络短暂中断”）
- [X] T071 [P] [US2] 在 `services/bff/Dockerfile` 和 `apps/web/Dockerfile` 中各新增一个**非末尾**的 `dev` 阶段：
  - bff：`uvicorn contexture_bff.main:create_app --factory --reload`；
  - web：Vite 开发服务器，监听 8080。

  默认构建目标不变（R11）
- [X] T072 [P] [US2] 修改 `apps/web/vite.config.ts`：HMR 的 `clientPort` 和 `allowedHosts` 从环境变量读取，未设置时与现状一致；并补充测试（R11）
- [X] T073 [US2] 新建 `deploy/cloud/devspace.yaml`，配置 `bff` 和 `web` 两个目标：
  - 用 `imageSelector` 选中要替换的 Pod，替换为开发镜像 `dev-<摘要>`；
  - 同步 `services/bff/src`、`packages/py-core/src`、`apps/web/src`、`packages/ui/src`、`packages/ts-api/src`；
  - 锁文件变化时，执行 `uv sync` / `pnpm install`；
  - 设置 `nodeSelector`。

  （FR-011；US2 场景 4）
- [X] T074 [US2] 实现 `tools/cloud/dev.sh`，并在 `Makefile` 新增 `cloud-dev`、`cloud-dev-reset` 目标。流程：检查环境状态 → 开发镜像不存在时先执行 `cloud-build --dev` → 运行 `devspace dev` → 在 `trap` 中恢复并写状态。使 T069 通过（FR-011～FR-014）
- [X] T075 [US2] 执行 `make cloud-dev`，使 T070 通过；验证开发模式期间执行 `cloud-deploy` 会要求确认；测量开发机内存占用不超过 2 GiB（SC-002、SC-003；US2 场景 6）

---

## Phase 9: User Story 6 - 一条命令启停云端环境 (Priority: P2)（阶段 E）

- [X] T076 [P] [US6] 编写失败测试 `tools/cloud/tests/test_lifecycle.sh`：
  - 停止顺序为：工作负载 → Doris operator → Doris StatefulSet → CNPG 休眠 → 控制器；启动顺序与之相反（R13）；
  - 读写 `contexture.io/stopped-replicas` 注解；
  - 只处理 data-model.md 第 3 节列出的 namespace，从不触碰 `dev` 和 `kube-*`；
  - 已处于目标状态时直接成功；部分运行时收敛到目标状态；
  - 有构建或测试正在运行时要求确认（FR-038），开发模式运行时也要求确认（FR-013）；
  - 启动等待超时时，列出 Pending 的 Pod 及原因。

  （FR-032～FR-035）
- [X] T077 [P] [US6] 编写失败测试 `tools/cloud/tests/test_status.sh`：输出内容包括：
  - 运行状态；
  - 开发模式，包括“开发模式（无本地进程）”；
  - 稳定版本：来源、提交、是否含未提交改动；
  - 按 `nodeLabel=nodePool` 统计的节点数；
  - 不在弹性池上的织境 Pod；
  - 残留的工具箱 / 构建 Pod。

  （FR-036、R7、R18）
- [X] T078 [P] [US6] 编写云端验证测试 `tests/cloud/test_lifecycle.sh`：
  1. 记录数据源、OM 表数量、Langfuse 轨迹数量；
  2. 执行 `cloud-stop`：20 分钟内弹性池缩到 0；devbox-0 不受影响；访问域名返回 T019 实测到的响应；
  3. 执行 `cloud-start`：30 分钟内冒烟测试通过；第 1 步记录的数据一致；`user1` 可以登录。

  （US6 场景 1～3；SC-011、SC-012；FR-037）
- [X] T079 [US6] 实现 `tools/cloud/lifecycle.sh` 的停止部分，并在 `Makefile` 新增 `cloud-stop` 目标（`TIMEOUT` 默认 25 分钟；超时时列出仍在弹性池上的非 DaemonSet Pod，以退出码 4 退出）（FR-032、FR-033、FR-038）
- [X] T080 [US6] 实现启动部分，并在 `Makefile` 新增 `cloud-start` 目标：恢复到稳定版本；等待证书 Ready；运行冒烟测试；等待超时时列出 Pending 的 Pod。使 T076 通过（FR-034、FR-035）
- [X] T081 [US6] 实现状态部分，并在 `Makefile` 新增 `cloud-status` 目标，使 T077 通过（FR-036）
- [X] T082 [US6] 运行 T078，使其通过；连续执行两次 `cloud-stop` 和两次 `cloud-start`，验证幂等；在停止过程中中断命令，再执行一次后环境能收敛（US6 场景 5；FR-035）

---

## Phase 10: Polish & Cross-Cutting Concerns（阶段 F）

- [ ] T083 开发机重启恢复验证（R18）：
  1. `cloud-dev` 运行期间删除 devbox-0 的 Pod，重建后执行 `cloud-status` 显示“开发模式（无本地进程）”，再执行 `cloud-dev-reset` 能恢复；
  2. `cloud-test` 运行期间删除 devbox-0 的 Pod，重建后执行 `cloud-status` 能报告残留 Pod，再次执行 `cloud-test` 时会先清理残留；
  3. 重建后执行 `which kubectl helm helmfile doctl devspace buildctl jq`，全部指向 `~/.local/bin`。

  结果写入 research.md R18
- [X] T084 [P] 完成 `docs/adr/0014-云端开发环境.md`，记录 R2、R4、R10、R11、R12、R13、R17a、R19 的选型及被否决的替代方案，以及 kcov 的许可例外
- [X] T085 [P] 在 `docs/Phase1-特性列表与开发计划.md` 中更新 030 的进度（实际工期、偏差，以及复估后对 007 及之后特性的影响）；在 `README.md` 的环境操作部分加入 `make cloud-*` 命令索引
- [X] T086 根据 T023 的结论二选一：在 `tools/cloud/lifecycle.sh` 中实现“启动时跳过补跑”并补充测试；或者修订 `specs/030-doks-deploy/spec.md` 的边界情况，写明接受一次补跑（R13）
- [X] T087 [P] 用仓库现有的密钥扫描，检查仓库、`cloud-images` 流水线日志和工具箱镜像中没有明文凭证（SC-010）
- [ ] T088 汇总自动化验证：
  - `CTX_KCOV=1 make cloud-unit`，用 `make coverage-check` 合并 Python、前端和 bash（cobertura）的覆盖率，新增与修改的代码 ≥ 80%；
  - `tools/cloud/tests/render-compare.sh`（SC-007）；
  - `make cloud-lint`、`make cloud-test`、`make cloud-e2e`；
  - `tests/cloud/*.sh`；
  - `make components-check`；
  - 远端 CI 全部通过。

  因环境原因未能通过的项目，如实记录原因
- [ ] T089 编写 `specs/030-doks-deploy/acceptance.md`，包括：
  - 前置条件：kubeconfig、域名与 DNS、DOCR 令牌、GitHub Secret；
  - 预计用时；
  - 按 quickstart.md 逐步操作，每条命令都可以直接复制执行，并写明预期结果；
  - 与 US1～US7、SC-001～SC-012 的对应关系；
  - T088 的结论；
  - 已知限制：
    - 测试用户密码同用户名；
    - Jaeger、Prometheus、OpenSearch Dashboards、AI 网关管理界面没有登录保护，并且对公网开放，所以只能放模拟数据；
    - Airflow 补跑的处理方式（按 T023 / T086 的结论）；
    - 开发模式期间不适合演示；
    - kubeconfig 令牌 7 天后过期；
    - 本地 kind 只做了渲染对比，没有在开发机上实际运行；
    - kcov 属于许可例外，只在开发测试中使用。
  - 验收记录表。

---

## Dependencies & Execution Order

```text
Phase 1 Setup ──► Phase 2 Foundational
                  （T014–T015 渲染基线必须先于任何共享文件修改；T016–T024 集群实测；
                    T025–T038 公共基础，含工具箱镜像 T033；T039 宪法修订必须在 T052 之前获批）
                         │
                         ▼
                 US1 部署（MVP，T052 首次部署）──► US4 访问 ──► US7 卸载
                         │
                         ├──► US5 集群内构建 ──► US3 集群内测试 ──► US2 开发模式
                         │
                         └──► US6 启停 ──► T086（依赖 T023 的结论）
                                                 │
                                                 ▼
                                    Phase 10 收尾（T089 最后）
```

- 工具箱镜像在 Phase 2 的 T033 就已构建好，所以 US1 中的 OM 本体配置（T051）不需要临时跳过。
- 每个故事内部的顺序都是：测试（红）→ 实现（绿）→ 集群验证。

## Parallel Opportunities

- Phase 1：T002、T004、T005、T008、T009、T011、T012、T013
- Phase 2：T020、T025、T027、T028、T030、T032、T034（实测任务 T017–T024 需要按顺序使用集群）
- US1：T040–T042，以及 T043–T048
- Phase 10：T084、T085、T087

### Parallel Example: User Story 1

```text
可并行：T043 postgresql、T044 keycloak、T045 openmetadata、T046 airflow、T047 其余组件、T048 bff / web 的 Chart
然后依次：T050 helmfile → T051 deploy.sh → T052 集群验证
```

## Implementation Strategy

1. **MVP = Phase 1 + Phase 2 + US1 + US4**：得到一套可以通过域名访问、可以重复部署的云端环境，交给负责人试用。
2. **开发能力**：US5 → US3 → US2。
3. **省钱与收尾**：US6 → US7 → Phase 10。
4. 保留测试先行的提交顺序，不使用 squash 合并。
