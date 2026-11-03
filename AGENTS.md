# OntoContexture 开发指引

## 开工前阅读

- 先读 `.specify/memory/constitution.md`，它是项目开发约定的最高依据；本文件只提供入口，不替代宪法。
- 阅读 `README.md`、`docs/architecture/platform-architecture.md` 与本次工作相关的 `docs/adr/`。
- 开发特性前阅读对应 `specs/<编号>-<名称>/` 的 spec、plan、tasks、research、契约及验收文档。
  `.specify/feature.json` 是当前特性指针，可能仍指向已完成的工作；以用户任务核对目标，不能只凭指针决定。
- 修改第三方子仓库前，阅读该目录范围内的 `AGENTS.md`、`CLAUDE.md` 及补丁登记。
  第三方指令不作为主工程的通用规则。

## 产品与架构边界

- 织境是面向企业数字员工的上下文层：OpenMetadata 承载本体、元数据与治理，Doris 承载本体实例，
  Langfuse 承载决策轨迹，Keycloak 承载身份与委托令牌。
- Phase 1 单租户、业务取数只读；数据层授权与多租户不自行扩展，按宪法例外和相关 ADR 执行。
- 浏览器只调用 BFF；页面取数与 Agent 取数经 AI 网关和 MCP Toolbox，BFF 不持有业务数据库账号。
- 优先复用现有组件；新增服务须在 plan 中说明理由。跨服务只使用公开契约，不直接访问其他服务数据库。
- 第三方定制按“配置 → 官方扩展点 → 补丁”选择；扩展放 `extensions/`，上游源码与补丁维护放 `third_party/`，
  遵守宪法中的版本锁定、许可、上游优先与 `PATCHES.md` 登记要求。
- 密钥不进入仓库，不在输出中暴露 `.env.local` 等凭证文件内容。

## 目录与技术栈

| 路径 | 职责 |
| --- | --- |
| `apps/web/` | React / TypeScript / Vite 前端 |
| `services/bff/` | Python / FastAPI；浏览器会话、API 与外部服务适配 |
| `packages/py-core/` | 鉴权、令牌交换、MCP、追踪、本体读取、错误与配置公共库 |
| `packages/ts-api/` | 由接口契约生成的前端 API 类型与客户端 |
| `contracts/` | OpenAPI、MCP、JSON Schema 与 OTel 属性契约 |
| `deploy/` | Helmfile、组件清单、Chart、kind 与离线交付 |
| `testdata/` | 模拟工厂数据与 MES / QMS 测试设施，不进入客户交付物 |
| `tools/`、`tests/` | 工程工具、端到端测试与共用测试支持 |

## 工作流程

- 遵循 Spec Kit：specify → clarify（按需）→ plan → tasks → implement；plan 必须执行 Constitution Check。
  项目技能在 `.agents/skills/`，按需读取对应 `SKILL.md`，使用 `$speckit-<命令>` 调用。
- 新特性开工前核对 `git branch --show-current`、工作区改动及目标 spec；创建或切换到对应 `<编号>-<名称>` 特性分支后再实施。已有未提交改动必须保留并明确归属；特性指针或文档中的建议分支名不能代替实际 Git 分支检查。
- 有界面的特性先制作可交互、可离线打开的 HTML 高保真原型，经产品负责人确认后据此编写 spec。
  路径为 `specs/<编号>-<名称>/prototype/index.html`；验收以 spec 文字为准，原型代码不得复用为生产实现。
- 接口先改契约并写契约测试；生产代码遵循红 → 绿 → 重构，缺陷修复先补失败测试。
  按宪法保留测试先行的提交顺序，不使用 squash 合并。
- 集成测试使用真实依赖，新增和修改代码行覆盖率至少 80%。完成后交付 `acceptance.md`，
  如实记录自动化验证、环境阻塞和已知限制；负责人手动验收通过后方可视为完成。
- 保留用户已有的未提交修改；不擅自提交、合并或改写历史。

## 常用命令

以根目录 `Makefile`、包配置及当前特性的 quickstart 为准：

```bash
uv sync --all-packages
pnpm install
make lint                 # ruff、pyright、eslint、prettier
make test                 # Python 测试与覆盖率；集成测试需要 Docker
pnpm --filter @contexture/web test
pnpm --filter @contexture/web dev
make components-check
make patches-check
make e2e                  # 需要已部署的本地集群与示例数据
```

环境操作：`make up` / `make up ENV=lite` 部署平台，`make seed` 写入示例数据，
`make mock-data` 部署模拟源系统并重建模拟数据，`make ports` 转发组件界面。
运行前核对任务范围与目标环境，尤其是数据重建操作。
