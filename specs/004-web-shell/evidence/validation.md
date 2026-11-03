# 004 最终自动验证（2026-11-02）

以下先保留 2026-11-02 基线；当前主动登录行为和验证结果见文末“2026-11-03 主动登录重新认证修订”。负责人手动验收尚未执行。未自动提交、合并、修改用户默认 Kubernetes 上下文或部署到外部环境。

## 最终结果

| 检查 | 实测 |
| --- | --- |
| make lint | 通过：ruff check / format、pyright 0 errors（104 warnings）、eslint / prettier |
| make test | 279 passed，13 deselected（集群另跑），Python 行覆盖率 87.50%；含真实 Testcontainers Keycloak / PostgreSQL |
| Web test:coverage | 54 passed；208/220 可执行行，94.54%，包括未覆盖的 main 引导 |
| UI test:coverage | 18 passed；12/12 可执行行，100% |
| Web / UI build | TypeScript 与 Vite 构建通过 |
| make coverage-check | 相对 HEAD 并纳入未跟踪新源码：364/397，91.69% |
| 覆盖率门禁反例 | 临时 LCOV 计数归零时 43.04%，退出 1；原报告未修改 |
| ts-api check | 官方 openapi-typescript 7.13.0 --check 通过；临时过期输入退出 1，原类型文件恢复 |
| components-check / patches-check | 均通过，Omnigent / OpenMetadata 补丁一致 |
| oasdiff v1.33.0 | v1 无破坏性结构差异；行为迁移与字符串回退见 contract-migration.md |
| 镜像 | BFF、Web、frontend-dependencies 阶段均构建通过；Web UID 101 |
| make e2e | 12 集群 passed（29.58 秒）；10 生产浏览器 passed（4.3 秒），0 skipped；1 开发浏览器 passed（4.3 秒），0 skipped |
| 开发 / 生产边界 | 8080 的 /__dev/ui 显示不存在；5173 真实会话可操作全部状态与独立内容示例 |
| 原有设备链路 | 真实 OM 定义、Doris 10 台设备、网关、Toolbox、Langfuse 追踪与审计通过 |

最终 Web：React / DOM 18.3.1、Router / DOM 7.18.2、Vite 8.3.4，构建 Node 22.23.4 / npm 12.2.1。
生产验证镜像 `contexture/web:004-acceptance`（与本机 004-final 同一构建），
ID `sha256:bf50133f58c1857398a4eb9a7797af5d543256e56cec8fea356000a1ecfa0535`。
BFF 为 `contexture/bff:004-us1`，部署仅限本机 kind-contexture。

## 扫描

Syft v1.54.1 生成 bff / web / web-dependencies 三份 CycloneDX。
安装阶段有 **543 个 npm 记录**（含构建工具与嵌套依赖）；确认实际 React、Router、Query、radix-ui 在列，
没有用只有 nginx 系统包的运行镜像清单代替前端依赖清单。

| 产物 | 许可检查 | Grype v0.120.1：已修复 Critical | Trivy 0.76.0：已修复 Critical |
| --- | --- | --- | --- |
| BFF | 0 禁止项 / 3 复核项 | 0，退出 0 | 0，退出 0 |
| Web 运行镜像 | 0 禁止项 / 0 复核项 | 0，退出 0 | 0，退出 0 |
| 前端安装 / 构建依赖 | 0 禁止项 / 23 复核项 | 0，退出 0 | 0，退出 0 |

扫描沿用既有 `--only-fixed --fail-on critical` / `--severity CRITICAL --ignore-unfixed` 政策，
不是“无漏洞”结论：Grype 另报 BFF 11 Medium / 2 Low / 1 Negligible，构建依赖 11 High / 14 Medium / 2 Low。
许可逐包固定版本与待核对项见 [license-review.md](license-review.md)，未修改 allowlist 或添加例外。

首轮安全门禁真实阻断旧 nginx 镜像的 curl / libcurl 8.22.0、brotli 1.2.0，以及构建环境 npm 的 tar 7.5.11、
Node 22.23.2 内置库。修复为 Alpine 已修复系统包、固定 npm 12.2.1 和 Node 22.23.4 后重建并全数复扫通过，未豁免。
漏洞库下载曾慢 / 失败，最终使用当日成功下载并通过校验的缓存；Grype DB v6.1.10 构建于 2026-11-02 06:26:52 UTC，
有效性校验通过。Trivy 当日经官方 ghcr.io/aquasecurity/trivy-db:2 下载成功；复扫复用缓存。CI 正常更新数据库。

## 失败复现与修复

- US1 首批 38 failed；角色、回调安全恢复、本地退出、上游暂时故障分类及显示名回退先红后绿，详见 us1-validation.md。
- US2 初轮 17 failed / 2 passed，浏览器导航 3 failed，之后实现统一导航、首页和示例。
- 身份重新核验曾丢失收起偏好：先复现 1 failed / 9 passed，再将非敏感偏好提升到同一布局容器；身份检查仍隐藏旧内容。
- 尾斜杠深链曾造成标题 / 高亮错位，/assets/ 又与 nginx 静态目录冲突：单元 2 failed、生产浏览器 1 failed，规范化路径并给 nginx 精确地址加站内 308 后通过。
- /objects/a/b 曾被页头误认成设备页：先复现失败，限定旧设备地址匹配后通过；合法设备页回归保持。

## 环境处理与执行偏差

既有 SSO 的数据库 / Keycloak / Caddy 原已停止；只恢复这些既有容器供真实认证，不启动其他应用，不改共享 realm / 客户端 / 角色。
追踪首轮 14 passed / 1 failed：Langfuse 查询 422，服务日志证明 ClickHouse 超过原 1536Mi 配额。
查询补上窄时间窗仍受内存约束；本机 ClickHouse 临时提高到 3Gi 后全链路通过，未重建其数据。
该运行配额尚未写入平台 Helm 配置；重新部署旧配置可能复现，需作为现有平台容量问题另行收敛。
查询窗口依据 [Langfuse 官方 Public API 指南](https://langfuse.com/docs/api-and-data-platform/features/public-api)。

**执行偏差已向负责人说明**：原 make e2e 含 003 双规模重建测试，首轮重建过 12 / 1 个月数据，第二轮发现后中止。
已按 003 验收说明恢复 12 个月、seed 20261001（MES 162319 行），15 步案例核对全部通过，0 失败 / 0 跳过。
已将该组保留为显式 `make e2e-mock-data`；普通 make e2e 不再运行重建。
所有后续回归用显式 kind-contexture 和权限 0600 的临时 kubeconfig，用户默认 k3d-gene 未改。

## 可复验命令与证据

```bash
make lint
make test
pnpm --filter @contexture/web test:coverage
pnpm --filter @contexture/ui test:coverage
pnpm --filter @contexture/web build
pnpm --filter @contexture/ui build
pnpm --filter @contexture/ts-api check
make coverage-check
make components-check patches-check
make e2e KUBE_CONTEXT=kind-contexture
```

本机日志 `/private/tmp/contexture-004-*.log`；原始 SBOM / 漏洞 JSON 在忽略的 sbom/，CI 配置上传产物。
截图在 test-results/production、test-results/ui，失败保留 trace；已人工查看两个尺寸的布局截图。
004 隔离嵌入的构建 / 路由 / HTTP / WS 实测见 compatibility.json 及 embed-*.md；
当前宿主 React / Router / Vite 一致。正式 Omnigent 身份、SDK 同会话、MCP 凭证、执行拒绝仍归 007，未宣称已通过。

没有创建测试或实现提交，只有先红后绿运行证据。依项目“不擅自提交”要求，测试先行的 PR 提交组织、
CI 远端运行、独立评审与非 squash 合并仍待后续授权流程；不把本机验证伪称为提交历史 / PR 门禁已通过。


## 2026-11-03 主动登录重新认证修订（本机验证完成）

负责人先确认逐文件方案，再指示“改”。实际生产逻辑仅在 KeycloakOidc 的授权 URL 固定加入 prompt=login；
首次、退出后及失败恢复的主动登录一致。Me / refresh / 本地 logout 逻辑保持，不增加前端退出标记。
根登录契约、ADR-0003、spec / plan / research / bff-session、接入说明和验收预期已同步；
生成的 TS 声明仅同步契约说明，不改接口结构。

### 测试先行

- 真实适配器及 BFF 入口 4 项单元测试先失败：授权 URL 缺少 prompt；含浏览器额外传 prompt=none / select_account 不能改变服务端策略的检查。
- 同一个 httpx 身份客户端保留 Cookie，先证明不带 prompt 的探测仍能由 SSO 返回授权码，再验证正常 BFF 登录必须出现密码表单：初轮实际 302 而预期 200，失败复现。
- 同一真实浏览器登录 → 本地退出 → 再登录初轮未出现密码框，失败复现。实现后测试错误密码保持未登录、正确认证创建新会话、旧 Cookie 仍拒绝、刷新保持登录。
- 测试登录 helper 现在必须等待认证表单，兼容账号预填 / 仅密码步骤，不再将直接 SSO 成功作为通过。Python helper 支持复用调用方 HTTP 客户端；Secure Cookie 的 HTTP 兼容仅用于隔离测试，不改变产品 Cookie。

### 最终结果

| 检查 | 本次实测 |
| --- | --- |
| BFF 单元 / 契约 + 共享鉴权回归 | 135 passed |
| 真实 Keycloak 26.8.0 / PostgreSQL 集成 | 13 passed，51.85 秒；含有效 SSO 下重新认证、原刷新寿命 / 撤销 / 故障 / 退出保留 IdP 会话回归 |
| make test | 284 passed、13 deselected，145.52 秒；Python 87.50% |
| Web / UI test:coverage | 54 / 18 passed，94.54% / 100% |
| 变更行覆盖率 | 364/397，91.69%，相对 HEAD 并包含未跟踪新源码 |
| lint / 类型 / 生成一致性 / Web 与 UI 构建 | 全部通过；pyright 0 errors，104 warnings 保留 |
| oasdiff / components-check / patches-check | 均通过；无破坏性结构差异，本次是显式登录交互策略修订 |
| make e2e | 12 集群 passed（30.47 秒）+ 11 生产浏览器 passed（5.9 秒）+ 1 开发浏览器 passed（4.3 秒）；浏览器 0 skipped |
| 新增浏览器重新认证场景 | 全套中 2.1 秒通过；单独复验 1.8 秒通过 |
| BFF 镜像 / SBOM / 许可 | 构建和 Syft v1.54.1 成功；67 个依赖、0 禁止项、原有 3 项待人工复核 |
| BFF Grype / Trivy | 均无达到既有“已修复 Critical”门槛的发现，退出 0；Grype 仍有 11 Medium / 2 Low / 1 Negligible |

新镜像 `contexture/bff:004-reauth`，ID
`sha256:05a4ac3fe803073cbe896081a1938f5d1a738b29a956a0f152da1d65d12e2f9e`，
已仅加载并更新本机 kind-contexture 的 contexture-bff；Web 保持 004-acceptance。
没有改共享 realm / 客户端配置、其他应用状态或模拟数据；默认 k3d-gene 上下文保持。

漏洞复扫使用前次成功下载并有效校验的缓存：Grype DB v6.1.10 构建于 2026-11-02 06:26:52 UTC，
Trivy 复用 2026-11-02 官方 ghcr DB。这里不宣称使用了 2026-11-03 新发布的数据库；CI 仍正常更新数据库。
报告 `sbom/bff-reauth.cdx.json`、`bff-reauth.grype.json`、`bff-reauth.trivy.json`；
执行日志 `/private/tmp/contexture-004-reauth-*.log`。没有豁免漏洞或修改许可规则。

复验命令：

```bash
uv run --frozen pytest services/bff/tests/unit/test_oidc_authorization.py -q
uv run --frozen pytest services/bff/tests/integration/test_auth_flow.py -q
make lint
make test
pnpm --filter @contexture/web test:coverage
pnpm --filter @contexture/ui test:coverage
pnpm --filter @contexture/ts-api check
make coverage-check
make e2e KUBE_CONTEXT=kind-contexture
```

原基线的环境调整 / 003 执行偏差仍如实保留；本次未重建模拟数据。
T049–T052 完成，T047 / T048 等待负责人实际手动验收。无自动提交、PR、远端 CI 或合并。


## 2026-11-03 用户验收文档职责修正

用户反馈开发组件演示不应由用户逐项验收。已将 acceptance.md 收敛为正式入口的六项产品操作，
开发组件、故障模拟、页面接入、旧设备回归和兼容性复核的操作归到 quickstart，由开发侧提供本记录中的证据。
对应工程交付和测试要求保持；spec / plan / tasks 与浏览器验证说明同步。仅文档修订，未修改代码、重跑测试或改变上述实测结果。
T047 / T048 仍未代签或勾选。


## 2026-11-03 登录浅蓝方案 B（实现与本机验证完成）

负责人确认原型 B 后实施。Web 登录入口、会话状态与失败页使用共享品牌布局；
Keycloak 官方父主题保留原生表单及安全脚本，仅增加客户端专属视觉层。
packages/ui/identity 中的生产 SVG / CSS 独立编写，没有复制原型代码、增加运行服务 / 依赖或修改上游源码。
主原型 SHA-256 仍为 28ff26f9894590fcf1151516b18f6a7814218b417a376a2d927ed159f077840d。

### 测试先行与修正

- 新登录入口 / 安全目标 / 帮助 / 失败页 4 项测试先失败，主题打包与真实客户端主题隔离先失败，随后实现。
- 真实浏览器两尺寸视觉测试先在旧入口失败；新入口上线后发现共享身份服务缓存旧主题脚本，
  仅清除了 contexture 自有脚本 gzip 缓存，未重启服务。重新运行通过。
- 本机原生认证是先账号、后密码；先补失败测试，再按当前表单显示分步提示和继续按钮，保持原认证流程。
- 浏览器分别检查 Web / 身份页帮助弹窗的键盘打开、Escape、焦点恢复，以及原生密码显隐。

### 实测结果

| 检查 | 结果 |
| --- | --- |
| make test | 290 passed、13 deselected，123.09 秒；Python 87.70% |
| 最新受影响 Python / 真实身份复核 | 主题打包、覆盖率工具及真实 Keycloak realm 共 17 passed，52.22 秒 |
| Web / UI test:coverage | 58 / 24 passed；行覆盖率 95.02% / 98.92% |
| 官方主题适配 JS | 行覆盖率 98.70%，分支 80%；已纳入差异覆盖率门禁 |
| make coverage-check | 495/529 变更行，93.57%；相对 HEAD 并包含新源码 |
| make lint / Web 与 UI build | 通过；pyright 0 errors，原有 104 warnings |
| components-check / patches-check / 静态主题一致性 | 全部通过；不新增上游补丁 |
| Helm 实际渲染 | ConfigMap 15 个静态文件，每个挂载路径及内容逐一核对一致；离线 deploy 副本自包含 |
| make e2e | 12 集群 passed（28.67 秒）+ 13 生产浏览器 passed（8.7 秒）+ 1 开发浏览器 passed（4.7 秒） |
| 最后补充帮助键盘检查 | 两尺寸真实登录场景 2 passed，4.6 秒 |
| 视觉人工检查 | 1280×720、1440×900 入口与密码页；无整体横向溢出，白卡 / 浅蓝视觉一致 |
| SBOM / 许可 | Syft v1.54.1 两镜像成功；前端安装依赖 495 项，0 禁止、原有 23 项待复核；最终 nginx 无 npm 依赖 |
| Grype / Trivy | 两镜像扫描均退出 0，无已修复 Critical；依赖镜像 Grype 保留 High 11 / Medium 14 / Low 2 |

Web 镜像 contexture/web:004-login，ID
sha256:658e0ff2272ee566b5d6ea6c64e9e08079fc5cd47e6905b6afc15581c8befafc，
已仅更新 kind-contexture / contexture 的 web-web。BFF 仍为 004-reauth；默认 kube 上下文仍是 k3d-gene。
未重建 003 模拟数据。原生产登录 / 退出语义、角色边界及其他应用状态保持。

### 客户端范围与交付限制

本机主题通过现有 provisioner 的公开管理接口只为 contexture-bff 增加 login_theme=contexture。
操作前后比较 realm 的完整表示及另外 10 个客户端的完整配置，均无变化。范围证据
/private/tmp/contexture-004-local-theme-scope.json 不含凭证。没有改共享 realm 的主题、语言或认证流程。
当前外部 Keycloak 容器直接安装的主题会随容器重建丢失，重建时须重新安装 / 持久挂载；
未擅自修改外部项目 Compose。自带 Keycloak 已提供可复现的静态 ConfigMap 挂载及滚动更新配置。

漏洞复扫使用此前成功下载并有效校验的缓存：Grype DB 2026-11-02、Trivy 官方 ghcr DB 2026-11-02，
不宣称为 2026-11-03 新数据库；CI 继续正常更新。没有修改许可规则或豁免漏洞，
原有人工许可复核项见 license-review.md。本次未构建完整离线镜像包，已渲染和逐字节验证主题静态交付。

日志 /private/tmp/contexture-004-login-*.log、contexture-004-theme-*.log；报告
sbom/web-login.{cdx,grype,trivy}.json、sbom/web-dependencies-login.{cdx,grype,trivy}.json；
截图 test-results/production/login-appearance-* 中 entry.png / identity.png。
T053–T057 完成。T047 / T048 仍待负责人实际产品验收；没有创建提交、PR 或代称远端 CI / 评审通过。


## 2026-11-03 登录文案定稿修订

按负责人原文更新 Slogan、说明及前两项支柱；“构建统一和可研究的业务语义”按指定表述保留，
第三项支柱的标题 / 描述均保持。共享中文源同步生成 Keycloak 部署副本，登录子原型与预览图、spec 引用哈希同步；
主原型没有修改。本次为文案调整，无新增功能、接口、认证逻辑、依赖或服务。

Web 58 项、UI 24 项既有测试通过；主题 --check、目标文件 ESLint / Prettier、git diff --check 通过。
Web 镜像构建通过，已部署 contexture/web:004-login-copy，仅更新 kind-contexture 的 web-web；
现有身份服务安装同一静态主题包并清理对应自有脚本缓存，没有更改客户端 / realm 配置或重启共享服务。
两尺寸浏览器场景通过（最终 2 passed，2.8 秒），在产品入口、账号步骤、密码步骤分别断言新 Slogan，
并保留登录、帮助键盘和密码显隐验证；检查了长文案布局。未重跑完整 Python / 集群回归或镜像漏洞扫描，
其前轮结果保留为历史，本次未把它们计作新执行。
日志 /private/tmp/contexture-login-copy-*.log；当前用户验收仍使用 8080 正式入口。T047 / T048 继续待负责人确认。


### 2026-11-03 Slogan 标题修订

按负责人要求将首句改为“构建企业AI Ready数据”，完整 Slogan 为“构建企业AI Ready数据，让智能有据可依。”
同步共享文案、主题静态副本、登录子原型 / 预览及 spec 哈希，其余描述与支柱保持。
Web 58 项测试、主题一致性、目标文件格式及 diff 检查通过；实际浏览器两尺寸登录场景 2 passed（2.4 秒），
入口、账号步骤、密码步骤均断言新标题。Web 已更新为 contexture/web:004-login-title，
身份服务仅更新现有织境主题资源及自有脚本缓存。没有重跑完整后端 / 集群 / 漏洞扫描，也没有改认证配置。
日志 /private/tmp/contexture-login-title-*.log。T047 / T048 仍待负责人确认。


### 2026-11-03 第二项支柱文案修订

按负责人要求更新为“构建统一的业务知识”，描述为“关联对象、关系与指标口径，让数据通过本体统一表达可理解的业务语义。”
仅同步共享文案、主题静态副本、子原型 / 预览及 spec 哈希，其余文案与认证逻辑保持。
UI 24 项既有测试、主题一致性、格式及 diff 检查通过；镜像构建成功，Web 已部署为
contexture/web:004-login-knowledge。两尺寸真实登录场景 2 passed（2.3 秒）；另外在真实浏览器
分别断言产品入口与企业认证页的新支柱标题和完整描述，均可见。主题仅更新现有织境资源与对应脚本缓存。
日志 /private/tmp/contexture-login-knowledge-*.log；未重跑完整后端 / 集群 / 漏洞扫描。T047 / T048 保持待确认。


## 2026-11-03 产品负责人验收与关闭

负责人明确确认“spec04验证完了，可以关闭了”。据此将 acceptance.md 登记为验收通过，
完成 T047 / T048 并同步 spec / plan / 开发计划，004 按原外壳范围关闭。
这是真实用户确认，未虚构逐项操作、验收用时或额外评审。上文各日期实测及待验收文字保留为历史，
最新产品状态以本节与 acceptance.md 为准。既有环境 / 许可 / 镜像扫描限制继续保留。
本次仅修改文档，没有重跑自动化、提交、创建 PR、执行远端 CI、合并或部署。下一项为 005，尚未开工。


## 2026-11-03 补建特性分支与合并准备

启动 004 时遗漏特性分支创建，实际实施一直在 docs/plan-progress-003。现从同一 HEAD
82c29e5 补建并切换至 004-web-shell。切换前后核对 209 个变更文件的内容摘要及暂存区，
均完整保留。没有创建提交、改写历史或改变产品验收结果；基线记录保留当时真实分支。
AGENTS.md 补充新特性开工前检查实际分支的要求，spec / plan 更新当前分支信息。

建议在该分支按以下主题整理提交，再通过 PR 合入 main：

1. 工程配置：Codex / Spec Kit 集成、AGENTS.md、宪法与模板；提交前核对 Spec Kit 脚本执行位变化。
2. 规划依据：特性拆分和编号、ADR、架构及 Omnigent 维护范围；涉及第三方的现有改动是维护文档，子仓库锁定提交未变。
3. 004 交付：规格 / 原型、契约与测试、Web / BFF / 公共 UI / Keycloak 主题、构建与质量门禁，按依赖关系分成可评审提交。
4. 验收记录：最终实现证据、负责人确认与开发计划的关闭状态。

这是事后整理未提交改动；测试先红后绿运行证据继续保留，不能把现在的拆分提交描述为开发当时已有的提交历史。
产品验收已经完成，提交整理后由远端 CI 验证提交版本，至少一名评审人批准后按非 squash 方式合并。
当前仅完成分支与范围梳理；尚未暂存、提交、推送、创建 PR 或合并。


## 2026-11-03 授权提交与合并准备

负责人明确指示“提交，并合并”。在 004-web-shell 上按工程配置、规划 / 规格、契约 / 测试、
生产实现和验收记录整理现有改动。所有提交使用实际时间，不回填日期；先红后绿的历史运行证据保留，
当前拆分不冒充开发当时的提交历史。Spec Kit 安装过程丢失的既有脚本执行位已恢复，脚本内容保持。
用户已完成产品验收并授权合并；最终提交需通过远端 CI，合并采用 merge commit 保留提交。
PR 的独立代码评审状态以 GitHub 实际记录为准，不将用户产品验收称为独立代码评审。
