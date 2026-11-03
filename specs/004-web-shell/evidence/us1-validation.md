# US1 独立验证（2026-11-02）

## 测试先行与实现

- Web 角色矩阵、回调恢复、独立退出、JWKS / 刷新分类先写失败测试。第一批 38 failed / 67 passed；补齐 OIDC 异常分类及登录存储恢复后再确认相应红测。环境 / 类型 / 夹具错误不算有效红测。
- 真实 Keycloak / PostgreSQL 初轮复现业务用户 / 无角色意外准入，以及身份服务停用被当作 401。最初停止 / 重启容器导致临时服务重连问题，改用暂停 / 恢复原进程注入故障后，两类 401 → 502 红测真实复现；数据库故障仍为 500。
- 先写 Web 会话与 API 用例，缺少新 API、失败页、状态分类和退出确认时失败；再实现。另补长身份展开、卸载取消设备请求和 JSON 诊断字段丢失的失败测试，再修复。

## 已执行结果

- BFF 单元 / 契约 + py-core 身份回归：131 passed。
- 独立 Testcontainers Keycloak 26.8.0 + PostgreSQL：12 passed（45.94 秒）。五组身份 Cookie / Bearer、重启后会话、刷新寿命、真实撤销、应用内退出后 IdP refresh 仍可用、JWKS / refresh 故障保留记录并恢复、存储 500。
- Web：31 passed；UI：18 passed；Web / UI 构建通过。
- `uv run --frozen pyright`：0 errors；原有及第三方类型不完整警告保留。直接调用 .venv/bin/pyright 未激活 Python 环境造成的 missing imports 不是源码问题，按项目 uv 命令复验。
- 网关现有策略集群回归：4 passed（2.83 秒）。使用临时、权限 0600 的仅 kind-contexture kubeconfig；未切换用户默认 k3d-gene 上下文。通用业务用户身份规则保持。

## 本机浏览器与既有设备链路

构建 `contexture/bff:004-us1`、`contexture/web:004-us1`，只加载到本机 contexture kind 集群，并通过显式 `--context kind-contexture` 更新 contexture-bff / web-web 镜像。

首轮企业登录在 TLS 入口连接关闭；检查确认既有 SSO 容器停止。恢复原有 SSO 所需的 postgres、Keycloak、Caddy 容器后 discovery 为 200；没有修改 realm、客户端、角色或其他应用配置。

提供既有 wrong-audience 夹具（令牌只在子进程环境中，未输出），运行：

```bash
pnpm exec playwright test -c tests/e2e/playwright.config.ts shell-auth.spec.ts demo.spec.ts
```

最终 **7 passed，0 skipped，3.1 秒**：

- 登录、真实账号、退出、旧 Cookie 拒绝、刷新 / 后退：1.3 秒，满足正常条件下 2 分钟身份演练。
- business-only 明确 403，可退出，无登录循环。
- 取消 / 无效回调经安全 303 恢复，新请求 / PKCE / state，不显示敏感参数。
- 旧设备读取：真实 OM 定义、Doris 10 台设备、HttpOnly Cookie 和账号信息，2.5 秒。
- 匿名 401、错误受众 403。

这只是 US1 的 MVP 检查点；US2 导航、设计示例、完整 CI / 扫描与负责人验收仍须完成。没有自动提交或合并。
