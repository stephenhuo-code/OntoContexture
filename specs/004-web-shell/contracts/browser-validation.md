# Browser Validation Contract: 004 开发与生产验证

2026-11-02 定义工程浏览器验证安排，配置与实测结果现已交付，见 evidence/validation.md。
这两个组别由开发侧执行；开发组件页不属于用户手动验收步骤。
目标是分别证明生产构建不开放示例，以及开发构建的公共状态可操作；两组均使用真实 BFF / Keycloak 会话。

## 配置、入口与用例

| 组别 | 配置 / 命令（实施后） | 入口与用例范围 |
| --- | --- | --- |
| 生产外壳 | `tests/e2e/playwright.config.ts`；`pnpm e2e:browser` | `http://localhost:8080`；保留旧 demo 与 shell-auth / shell-navigation，明确排除 `ui-examples.spec.ts`；shell-navigation 包含已登录访问 `/__dev/ui` 显示不存在 |
| 开发组件 | 新增 `tests/e2e/playwright.ui.config.ts`；`pnpm e2e:ui` | `http://localhost:5173`；只匹配 `ui-examples.spec.ts`；webServer 启动 Vite dev，执行受保护示例的组件与状态恢复 |

根 `package.json` 新增 `e2e:ui`，`Makefile` 的 `make e2e` 保留现有集群 / 生产用例后再运行开发组。
003 的双规模集群用例会重建 MES / QMS / mock_dw，保留为显式 `make e2e-mock-data`；普通 `make e2e`
只运行网关 / Toolbox / 追踪审计与两个浏览器组，避免 004 回归改变模拟数据。该分离不删除 003 的回归测试。
两组使用不同报告与 trace 输出目录，CI 或本地失败均返回非零状态；缺少身份服务、登录用户或开发服务器时不得静默跳过。
开发组配置明确指定 `pnpm --filter @contexture/web dev --host localhost --port 5173 --strictPort`，保持 `/bff` 到 8080 的既有代理。
不允许两个配置分别依赖同一个“示例必须存在”的断言，也不允许以运行环境不符为由让示例用例全部 skip。

## 真实认证与回调复用

生产入口使用既有已注册的 8080 回调，004 不增加 5173 的 IdP 回调、不改共享 realm / Paperclip 配置。
`tests/e2e/helpers/login.ts` 为开发组提供明确的准备步骤：

1. 在该用例自己的 BrowserContext 中访问 `http://localhost:8080/home`，通过企业登录页面完成真实登录并确认 Me 成功。
2. 使用同一 BrowserContext 访问 `http://localhost:5173/__dev/ui`；两个入口统一使用 localhost，避免 localhost 与 127.0.0.1 混用。
3. Cookie 以主机 / 路径为作用域，不按端口隔离；现有本地 HttpOnly ctx_session 随 5173 同主机请求发送，
   Vite 将 `/bff` 请求转发到真实 BFF，后端仍执行相同角色校验。不得注入令牌、伪造登录或把 Cookie 值写入日志 / 受版本管理的 storageState。
4. 每个用例独立上下文；退出用例不得使其他并行用例共享的本地会话失效。生产组仍独立验证从匿名入口开始的完整登录与退出。

这是本地 HTTP 开发环境的安排；不改变生产 Secure / SameSite 等 Cookie 配置。若环境改为不同主机或 HTTPS，
先调整并验证同源入口方案，再修改文档，不能默认 Cookie 跨主机可用。

## 构建开关与验收证据

- `/__dev/ui` 只由开发 / 测试构建时条件注册；标准生产 build 不注册该路由，不通过 URL、localStorage 或运行时用户参数开启。
- T032 覆盖路由注册边界；T033 编写两组浏览器场景；T038 接入开发示例；T044 在新生产镜像和真实登录环境分别运行两组。
- T044 记录两个命令、实际入口、构建模式、结果及失败 trace；T046 引用这些证据。不能用开发服务器证明生产隔离。
- 两组不新增业务数据或 Agent 服务，不重建 003 数据。dev 组的演示数据明确标识，仅用于公共组件状态。
