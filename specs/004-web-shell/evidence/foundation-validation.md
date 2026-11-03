# T006–T012 公共基础验证（2026-11-02）

- 用户确认显示名称按姓名 → 用户名 → 用户 ID 回退。先跑四组用例，缺失 / 空文本两组失败，再修复；四组通过。Me Schema 的字符串 / 缺省通过、null / 数字拒绝共 5 组通过；生成类型来自根契约。
- oasdiff v1.33.0：0 breaking changes，退出码 0；不关闭检查。现有 callback 生成式测试对缺参返回 422 的失败保留，归 T014 / T023 受控 303 实现。
- 依赖精确对齐 React / DOM 18.3.1、Router / DOM 7.18.2、Tailwind 4.3.1、Radix 1.6.3、Query 5.101.2；UI 为 React peer。Web / UI 使用 Vitest 5.0.5 及同版 V8 provider，React 类型 18.3.27 / DOM 类型 18.3.7。冻结 pnpm 锁文件。
- 测试先写：共享包尚无 index / 组件 API，两个测试文件按预期无法导入；实现原语后，PageState 未导出导致 12 个状态用例失败。原语 6 个、状态 12 个最终全部通过。jsdom 缺 ResizeObserver 导致的错误只算环境问题，补测试环境适配后复验；真实弹层定位仍由后续浏览器验证。
- `pnpm --filter @contexture/web test`：4 passed；`pnpm --filter @contexture/ui test`：18 passed。
- `pnpm --filter @contexture/ui test:coverage`：行 / 分支 / 函数 100%（格式化前 V8 映射）；最终完整报告由 T043 重跑，不能据此声称后续功能已覆盖。
- Web / UI TypeScript 与 Vite 8.3.4 生产构建通过。共享 CSS 保持标准语法；Tailwind theme 映射放在实际 Tailwind 样式入口，修复单独 tokens 导入产生的 unknown @theme 警告后重建通过。
- `docker build -f apps/web/Dockerfile -t contexture/web:004-foundation .` 最终退出码 0，镜像 `sha256:3610cbb60bf4f5689a0e67bea15f72e6c787c24e064f423654d16e6ef4c67d5f`。包含 packages/ui 的冻结构建成功。
- 启动一次独立 nginx 容器验证 `/home` 为 200 SPA、生成 JS 为 200、运行 UID 101；随后停止并清理该临时容器。没有部署到平台、改共享 IdP 或重建数据。

生产外壳 / 身份改造尚在后续任务。没有自动提交；测试先行执行证据不能替代将来 PR 的测试先行提交历史和负责人手动验收。
