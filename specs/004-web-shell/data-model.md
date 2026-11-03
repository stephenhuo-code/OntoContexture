# Data Model: 004 外壳与身份状态

不新增数据库实体或迁移；下面是 UI / 请求模型。服务端会话继续复用现有 SessionRecord。

## 1. CurrentUser

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| tenant_id | string | 服务端部署上下文；单租户，不从页面输入获取 |
| user_id | string | 受信身份主体；不能为空，不可由用户头覆盖 |
| display_name | string / null | 为空时回退 user_id；长文本截断但完整可读 |
| roles | string[] | 来自验签后的 realm_access.roles；缺失视为空 |

这里的 CurrentUser 是 UI 归一化模型；根 OpenAPI 的 Me 是线上响应模型。Me 的 display_name 为可缺省 string，
roles 可缺省；UI 将缺省 display_name 归一为 null、缺省 roles 归一为空数组，不改变 user_id / tenant_id 的必填约束。
2026-11-02 负责人确认保留 v1 字符串契约：BFF 姓名 → 用户名 → user_id 回退。UI 对历史 null 仍做防御性处理；缺省归一不改变线上契约。

WebAllowed = roles 含 admin 或 ai-engineer。business-user 单独不准入；混合角色含任一准入角色则允许。
前端不以缓存角色替代后端每次 Web 业务请求的检查。

## 2. SessionView

| 状态 | 进入条件 | 页面 / 动作 |
| --- | --- | --- |
| checking | 初次访问、显式重试、需要重新核对身份 | 全页加载，不展示旧用户内容 |
| authenticated(user) | Me 200 且服务端已准入 | 外壳、账号、路由 |
| anonymous | Me 401 或 logout 204 | 匿名登录入口；不得自动循环新建会话 |
| forbidden | Me 403 | 无权限、退出；不显示受保护数据 |
| unavailable(error) | 网络 / 502 / 500 | 错误、重试；不能误称未登录 |

状态转换：checking → 上述四个结果；unavailable → retry → checking；authenticated / forbidden → logoutPending →
204 → anonymous，失败 → 显示退出错误并允许重试。会话失效后清空 Me 缓存与前用户内容。
logoutPending 是动作状态，不新建数据库会话。若退出响应丢失，可再次幂等退出确认。

## 3. Existing SessionRecord

现有字段：user_id、access_token、refresh_token、id_token、access_expires_at、expires_at。
只在 BFF 会话库保存，浏览器仅持 HttpOnly ctx_session Cookie。

- 刷新成功更新令牌并按现有会话寿命规则使用，不扩大 expires_at。
- 明确 invalid_grant / 会话过期：删除或判定无效，401。
- 暂时网络 / 身份服务故障：保留记录，返回 502，不使用过期令牌提供业务内容。
- 退出：删除该 session_id，Cookie 过期，不通知其他客户端 / IdP 全局会话。
- 不把 Web 专属准入角色写成全局 JWT 认证规则；角色来自当前已验证令牌。

## 4. RouteEntry / NavigationState

字段：id、label、path、module、secondaryItems、availability（shell / not_open）、isAction。
新建对话是动作型入口，004 仍有独立占位地址；模块归 Agent，当前标题为“新建对话”。
首页二级有 overview / approvals；asset / agent 暂无二级目录，不生成假目录树。

菜单状态 secondaryOpen 是应用内 boolean，默认 true；路由切换保留，刷新重置，不存 localStorage。
路径是当前位置唯一事实来源，菜单高亮和标题从路由派生，不另存独立 screen 导致不一致。

## 5. SharedStatePresentation

kind = loading / empty / error / forbidden / not_open / not_found；
title、description、actionLabel、action、busy、traceId（仅安全诊断字段）。

error 可重试；forbidden 可返回 / 退出而不能“重试获权”；not_open 只有说明与首页入口。
组件示例使用明确的演示数据，不把示例状态发布为真实业务结果。

## 6. CompatibilityEvidence

字段：upstreamCommit、hostDependencyVersions、topic、procedure、result、evidenceLocation、limitations、ownerFeature。
result = static_confirmed / runtime_pass / runtime_fail / not_run；not_run 不能折算为通过。
每个主题独立记录；004 解决当前宿主技术选择，007 负责正式身份与会话联调，不新增运行业务表。

## 7. LoginFailurePresentation

公共 `/auth/error` 的展示模型，不是数据库实体，也不是已认证身份。

- reason = cancelled / invalid_response / unavailable / internal；缺失或未知值统一为 invalid_response。
- trace_id 为可选诊断标识，只接受 32 位十六进制格式；不承载用户、令牌或错误详情。
- return_to 仅接受安全站内路径与查询，缺失 / 非法值或再次指向 `/auth/error` 时回退 `/home`。
- 不接受 OAuth code、state、token、error_description 等作为页面展示字段；原因参数只影响文案，不授予任何权限。
- 重新登录必须新建登录请求 / state / PKCE；返回首页仍经过正常身份检查，不将失败页视为会话成功。

失败分类、重定向和 state 校验见 [bff-session.md](contracts/bff-session.md#登录导航失败与恢复)。
