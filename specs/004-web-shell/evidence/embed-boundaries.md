# T004：传输接缝与身份交接

2026-11-02。upstreamCommit：`a8676d23e88df7918f4f8ef1c7c4e3186e710354`。
hostDependencyVersions 与重建 procedure 见 [embed-runtime.md](embed-runtime.md)；每个主题的结果见 [compatibility.json](compatibility.json)。

## HTTP / WS 隔离实验：runtime_pass，ownerFeature = 004

官方嵌入产物通过 `setOmnigentHostConfig` / `OmnigentApp` 的 fetcher 与 resolveWebSocketUrl 发出实际请求：

- `/v1/me`、info、sessions、projects、extensions 等 HTTP 都进入本机 `/bff/spike/...`；无正式 Omnigent 服务、产品代理或身份凭证。
- 嵌入自身的 sessions updates WS 进入 `/bff/spike/v1/sessions/updates`，临时 Vite WS 代理去掉夹具前缀，服务器收到 `/v1/sessions/updates`；卸载 / 页面切换后可观察到关闭。
- 另外直接导入同一锁定提交的 `web/src/lib/host.ts`，单独验证 hostFetch 转发 RequestInit 的 AbortSignal、401 原样传递和 resolver URL。这个源模块探针有独立模块状态，不冒充已打包嵌入的私有实例。
- 读取第一个 NDJSON chunk 后 abort，浏览器 reader 得到 AbortError，服务器记录流关闭。不是仅检查 signal 对象存在。
- resolver 生成同源 `ws://127.0.0.1:4174/bff/probe/v1/probe/socket`，服务器实际握手路径为 `/v1/probe/socket`、Origin 为宿主；浏览器收到夹具消息并正常以 1000 关闭。
- [runtime.json](embed-spike/runtime.json) 记录实际路径、浏览器与服务器事件；服务器计数为同一夹具进程内累计，不表示产品并发或性能结果。

初次仅代理显式 probe，遗漏嵌入工作台自发建立的 sessions updates WS，出现握手超时；补齐两路 WS 代理后完整检查通过。由此要求未来代理覆盖实际连接入口；不把临时夹具失败归为上游不兼容。

实验夹具只监听 127.0.0.1、只接受所列本机 Origin 和测试 WS 路径；没有把该无认证夹具接到真实平台。

## 产品代理设计依据：static_confirmed，ownerFeature = 004；实现归 007

源码依据（相对锁定 `third_party/omnigent/src/`）：`web/src/lib/host.ts` 的 hostFetch / resolveWebSocketUrl 原样委派；
`web/src/lib/identity.ts` 通过 hostFetch 查询 `/v1/me`，并在 authenticatedFetch 中添加浏览器 X-Forwarded-Email。

007 的候选同源入口为 BFF 下的专用 Omnigent 前缀（最终路径由 007 根契约确定），统一转发 HTTP / SSE / WS：

1. BFF 先校验自己的 Cookie 会话与 Web 角色，再按公开上游 API 的方法 / 路径 allowlist 转发；不把任意目标 URL 做成开放代理。
2. 剥离浏览器 Authorization、身份 / 角色头及不应透传的 Cookie，只在服务端形成上游受信身份；不能依据 X-Forwarded-Email 授权。
3. 浏览器 WS 用同源 Cookie，握手检查 Origin 和有效会话；上游认证由服务端完成，不把令牌放进 URL / 浏览器存储。正式连接失效、退出与跨实例管理需 007 实测。
4. 流式传输保持背压、取消与连接关闭；下游中止要中止上游，不缓冲整个 SSE 流；错误响应保留安全分类，不透传敏感正文。
5. 本地 logout 后，007 必须停止该用户连接与前端缓存；UI 卸载正常不等于证明身份撤销已覆盖持续 WS / SSE。

## 身份来源：static_confirmed，ownerFeature = 004

- `web/src/lib/identity.ts:369` 查询 `/v1/me`；约 466 行会把缓存 user_id 放入 X-Forwarded-Email。
- `omnigent/server/auth.py:383` 的 AuthProvider 抽象以 HTTPConnection 提取 user_id，返回 None 为未认证；它是候选官方扩展接口。
- 同文件约 629–690 行：OIDC / accounts 模式先读自有 Cookie，再读 Bearer；使用自身 cookie_secret 验证 **HS256 会话 JWT**，并检查 sub。不能据此认定它会验证 Keycloak 的外部访问令牌。
- `omnigent/server/app.py:1316` 的 create_app 接收 `auth_provider`。源码存在注入参数，不等于标准生产启动方式已经接好独立扩展。

候选方案是在 BFF 身份边界后，通过官方 AuthProvider 独立扩展验证受信签名身份并映射稳定主体；签发者、算法、受众、过期、主体和转发信任链均须明确。
必须验证启动接线、HTTP / WS 一致性及上游权限存储；不以用户名头、静态 Bearer 或伪造签名替代。004 没有实现这套桥接。

## 007 / 012 交接：not_run，ownerFeature = 007

正式验证矩阵以 [embed-readiness.md](../contracts/embed-readiness.md) 为准：

- 真实 Keycloak / BFF 到 Omnigent 的签名身份、不同用户私有会话隔离、无效签名 / 受众 / 过期拒绝、退出后持续连接失效。
- 锁定官方 SDK 的 BFF 依赖、同一服务端会话在轻量助手与嵌入工作台间延续、重连 / 去重 / 取消；不复制私有 store。
- 真实 OM 资产上下文和来源绑定；浏览器不直连业务底座。
- 会话 MCP owner / Agent 包写入约束、短期委托凭证注入和失效；不把短期 token 长期写入静态 headers。012 负责完整续期 / 执行恢复加固。
- 007 未交付的终端、代码与定时执行必须由服务端拒绝，sidebarConfig / CSS 不是授权；012 验收后才开放。
- 模块级 host config、QueryClient 和 identity cache 不默认支持两个工作台实例或安全换用户；正式生命周期必须另验。

limitations：所有真实集成均未运行；本次不能作为身份、Agent 会话、MCP 凭证或执行安全验收。没有申请源码补丁或宪法例外。
