# BFF Session Contract: 004 行为增量

本文件定义拟实施行为；根 `contracts/openapi/bff.yaml` 是接口正本，实施时先更新该契约与失败测试，再改代码。
2026-11-02 经负责人确认，Me.display_name 保持 v1 字符串契约，姓名 → 用户名 → user_id 回退；其余行为仍为实施设计，
不新增“外壳业务接口”。Me 和 ErrorEnvelope 的字段集合继续使用，浏览器登录导航的失败响应与 JSON API 分开定义。

## 请求与角色

认证机制继续支持 ctx_session Cookie 或 audience 含 contexture-bff 的 Bearer；浏览器只用 Cookie。
校验顺序：认证 / 验签 / 受众 → Web 角色门禁 → 下游业务调用，拒绝后不得继续请求 OM / MCP。

| 角色集合 | `/me` 与现有 Web object 接口 |
| --- | --- |
| admin | 允许 |
| ai-engineer | 允许 |
| business-user | 403 auth.web_access_denied |
| 空 / 无上述准入角色 | 403 auth.web_access_denied |
| business-user + admin 或 ai-engineer | 允许 |

不改变 AI 网关、MCP、其他客户端的 business-user 权限。不把 role gate 加到通用 Authenticator。
`/auth/login`、`/auth/callback`、`/auth/logout` 与健康检查不套 Web 准入 gate；callback 完成身份认证不等于获准 Web 使用。

2026-11-02 负责人明确确认：logout 仅结束当前织境 BFF 会话，不调用 IdP logout、不结束企业 SSO。
成功后由前端清理缓存并停留匿名入口；2026-11-03 负责人修订：用户主动再次登录必须重新认证，BFF 授权 URL 固定携带 prompt=login；当前本地密码认证需输入密码，错误密码不能建立新会话。已有 SSO 仍保留，但不能直接跳过这次认证。正常 Me 检查与令牌刷新不触发此流程。
这是已确认的契约目标，现有运行代码的改造及无 IdP 副作用回归仍由 T016 / T018 / T024 完成。

## HTTP 行为

| 方法与路径 | 成功 | 失败 / 注意事项 |
| --- | --- | --- |
| GET `/bff/v1/auth/login?return_to=…` | 302 到现有企业认证 | 保留安全站内目标；非法目标降到 `/`；BFF 可处理的登录依赖错误以 303 返回 `/auth/error`，见下节 |
| GET `/bff/v1/auth/callback` | 验证 state / code 后 302 到站内目标并建立现有会话 | 接受成功 code + state 或失败 error + state；取消、无效响应及依赖故障以 303 返回 `/auth/error`；无 Web 角色在成功回调后由 Me 403，不循环登录 |
| GET `/bff/v1/me` | 200 Me，字段 tenant_id / user_id / display_name / roles 沿用 | 401、403、502、500 分类如下；拒绝时不返回 Me 私有正文 |
| POST `/bff/v1/auth/logout` | 本地会话删除 + Cookie 过期，204，无会话幂等 204 | 不调用 IdP logout，不联动 Paperclip；本地删除失败 500，不先宣布退出成功 |
| GET `/bff/v1/object-types/{typeKey}` | 200，原对象定义形状 | 先 Web gate，再继续原读取行为 |
| GET `/bff/v1/object-types/{typeKey}/objects` | 200，原实例列表形状 | 先 Web gate，再继续 MCP / 网关读取，原 limit 约束保留 |

身份接口需要前端处理成功与非成功响应；不能仅 `await fetch()` 就跳回首页。
静态 index.html 可公开，不含身份凭证；保护边界在服务端业务响应，不是假定 nginx 对 SPA 每条路由鉴权。

## Me 字段与缺省值

- tenant_id、user_id 为必填 string；user_id 不能为空。
- display_name 为可选 string；BFF 姓名、用户名均缺失时回退 user_id。客户端对缺省、空文本及历史 null 做防御性回退，不改变身份主体。
- roles 为可选 string[]；缺省在客户端归一为空数组，不能据此绕过服务端角色门禁。
- 根契约为 `type: string`，生成类型为 `display_name?: string`；保留 v1 响应保证。
  Schema 接受缺省 / 字符串，拒绝 null / 整数；另测 BFF 姓名 / 用户名缺失时返回 user_id。
  旧后端曾返回 null 是实现与已声明契约的偏差；本次修复后端，不扩张 v1 类型。

## 登录导航失败与恢复

login / callback 是浏览器顶层导航；失败不让用户停留在原始 JSON 文档。BFF 能捕获的失败返回
`303 Location: /auth/error?reason=<枚举>&trace_id=<可选>&return_to=<安全站内目标>`，固定目标为织境同源页面，
附 `Cache-Control: no-store`、`Referrer-Policy: no-referrer`；不创建新会话 Cookie，不清除可能已存在的其他有效织境会话。
Me、object、logout 等 JSON API 保持下节的 HTTP 状态与 ErrorEnvelope，不把它们也改成登录重定向。

| 原因 | reason | 页面说明 / 恢复 |
| --- | --- | --- |
| 有效 state 对应的 `error=access_denied` | cancelled | 登录已取消；重新登录 |
| 缺失 / 无效 / 过期 / 重放 state，code 与 error 同时存在或均缺失，其他 OAuth 拒绝 / 无效 code / 验签拒绝 | invalid_response | 登录未完成或请求已失效；重新登录 |
| IdP 换码 / JWKS 暂时网络故障或 5xx | unavailable | 登录服务暂时不可用；重新登录 |
| BFF 会话存储或未预期内部异常 | internal | 登录暂未完成；重新登录，可显示安全诊断标识 |

处理顺序：回调参数由处理器按上述两种响应形式校验，避免“取消时缺 code”直接落到框架 422；
先验证并一次性消费既有 LoginRequest.state，成功形式才换码，失败形式不换码。无效 state 不采信任何 return_to，
恢复目标固定 `/home`；只有已验证登录请求中的安全 return_to 可以恢复。重复 / 不符合格式的参数按 invalid_response 处理。

303 URL 只含上述允许的参数；trace_id 仅为有效的 32 位十六进制诊断标识。不得透传 OAuth code、state、token、
error_description、堆栈或任意上游 URL。前端 reason 仅影响说明，不能作为认证或授权依据。
`/auth/error` 不触发自动 SSO；“重新登录”调用既有 login，生成新的 state / PKCE，“返回首页”正常走身份边界。
由于 state / code 可能已消费或一次性失效，不能重试原 callback URL。

服务整体不可达或浏览器已位于不可达的 IdP 页面时，BFF 无法承诺渲染错误页；回到织境后可从登录入口重试。
T006 在实施前把 303、Location / 安全响应头和条件参数写入根 OpenAPI，T014 / T016 / T020 先覆盖此契约再实施。

## 错误分类

以下用于 JSON API / 身份依赖内部错误分类；login / callback 的浏览器导航按上一节映射为 303。
统一 envelope：`code`、面向用户的 `message`、`trace_id`，可选安全 `details`；不返回令牌、Cookie 值、数据库 DSN 或堆栈。

| 状况 | 状态 / code | 会话处理 |
| --- | --- | --- |
| 无会话、确实过期、无效签名 / 身份 | 401，保留现有认证码 | UI 清旧用户，提供登录；存储中的无效会话失效 |
| 明确刷新 invalid_grant / 已撤销 | 401，沿用认证错误约定 | 删除会话，不无限重试 |
| 令牌受众不匹配 | 403 auth.invalid_audience（既有行为） | 不进入业务调用，不当作角色准入通过 |
| 身份有效但不具 Web 角色 | 403 auth.web_access_denied | 可保留会话供安全退出；不重登循环 |
| IdP / JWKS 暂时网络失败或 5xx | 502 upstream.unavailable | 保留会话记录，禁止用过期 token 继续业务；用户可重试 |
| 会话库或非预期内部错误 | 500，沿用统一内部错误码 | 不泄露细节；不得伪报 401 / 204 |

## 行为版本与迁移约束

- Me / ErrorEnvelope 字段集合保持；Me.display_name 保留字符串响应保证，roles 缺省归一为空；UI 将 403 与 401 分开处理。
- 由“任意有效身份可读 Web 接口”收紧为“现有 Web 角色准入”，以及从 provider logout 改为应用 logout，均需在契约评审中明示。
- 根 API 正本更新、oasdiff、BFF / ts-api 契约测试必须完成。不能因 JSON 形状不变就声称完全无行为变更。
- 登录导航失败从 JSON 改为 303 也属于显式行为变更，与角色 / 退出一起核对消费者与迁移，不能遗漏直接调用 login / callback 的自动化客户端。
- 当前设计按未对外承诺 business-user Web 访问的 v1 安全政策修正处理；实施前核对消费者。
  若存在需兼容的旧外部消费者，按宪法版本化并给迁移期，不跳过门禁。
- 001 已验收文档不回写；004 验收说明 engineer1 / admin1 的成功路径以及 business-user 改为 Web 拒绝。
- 保留共享 JWT 业务用户默认夹具，仅在 BFF Web 测试中显式指定允许角色。

## T006 消费者核对与迁移记录（2026-11-02）

仓库路径搜索覆盖 apps / packages / services / tests / tools / deploy。已知消费者为自有 Web、生成 ts-api、BFF 单元 / 契约 / 集成测试、本地 smoke、浏览器 demo，以及 tests/e2e/test_trace_and_audit.py 的 BFF 取数。未发现需保留旧业务用户 Web 准入或 provider logout 的已发布外部 SDK / 客户端。当前仍处内部开发阶段，按已确定的 v1 安全政策修正实施；不把仓库搜索当作仓库外部署清单。PR 如发现外部兼容承诺，须先补版本化迁移，再发布。

- Web 将按状态分类、303 恢复页、logout 204 迁移；成功登录仍为 302，接口路径与 Me 字段集合保持。
- callback 参数在 OpenAPI 中不再无条件 required，以支持取消 / 缺参的受控 303；code + state / error + state 条件由处理器显式校验，详见上述契约。
- 原生成式契约测试仍保留；根 Schema 错误响应经多个组件复用同一 error.json，无新错误正文形状。
- tests/e2e/test_trace_and_audit.py 的 Web 成功身份也必须迁为 engineer1，通用 browser_session 接口与 user1 网关成功场景保持；已纳入 T020。
- tools/demo.sh 只验证匿名 / wrong audience 拒绝，仍可使用 user1 的错误受众令牌，无需整体换身份。
- 无需数据表迁移。只改变退出当前本地 session，已签发的其他客户端令牌与 SSO 不在本变更撤销范围。
- oasdiff 与生成一致性结果在后续实施证据中记录；不得修改检查排除行为来压掉失败。
