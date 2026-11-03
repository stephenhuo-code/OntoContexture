# US2 独立验证（2026-11-02）

先写 navigation / shell-pages / ui-examples 三组测试，初轮 17 failed / 2 passed；真实生产导航初轮 3 failed。
随后实现单一 Shell、路径派生导航与标题、内存菜单偏好、首页四卡片 / 待办 / 最近资产及未开放页。

最终 Web 54 passed；开发示例真实登录 1 passed（4.4 秒），生产导航与 US1 回归 7 passed（4.9 秒）。
生产 `contexture/web:004-final`，入口 8080；Vite dev 入口 5173，复用 8080 真实认证后的 Cookie。
生产组证实 `/__dev/ui` 不存在；开发组五类状态、失败重试 / 恢复、独立内容例子、长中文均通过。
1280×720 / 1440×900 的键盘导航、可见焦点、提示、账号、菜单空间和无整体横向溢出通过。
占位页只请求 Me，不请求 OM、搜索、Agent、审批或执行服务。原型哈希及上游源码保持。

命令：`pnpm --filter @contexture/web test`、`pnpm e2e:browser shell-navigation.spec.ts shell-auth.spec.ts`、`pnpm e2e:ui`。
截图：本机 test-results/production 与 test-results/ui（按配置隔离，测试运行可重新生成）；失败保留 trace。
自动化验证并不代替负责人手动验收。最终全套结果见 validation.md。

补充：身份重新核验期间保留菜单收起偏好，先红测复现、提升布局偏好状态后通过；刷新仍默认展开。

最终补齐尾斜杠与旧设备地址误匹配回归，最终镜像 / 全套浏览器结果以 validation.md 为准。
