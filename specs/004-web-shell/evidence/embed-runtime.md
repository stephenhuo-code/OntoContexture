# T003：Vite 宿主运行验证

2026-11-02，`result = runtime_pass`；输入与主题记录见 [compatibility.json](compatibility.json)。

## 实际输入

- upstreamCommit：`a8676d23e88df7918f4f8ef1c7c4e3186e710354`。
- hostDependencyVersions：React / ReactDOM 18.3.1、react-router / react-router-dom 7.18.2、Vite 8.3.4、plugin-react 6.1.2、pnpm 11.20.0。
- 首轮 Node 24.21.0；Chromium 156.0.8078.4、1440×900。Node 22 复核结果另行追加，不混作首轮工具链。
- 官方产物由上游 Vite 8.1.0 生成，再由宿主 Vite 8.3.4 二次打包。未修改官方源码或产物来绕过兼容问题。

## 可复现 procedure

先按 [embed-build.md](embed-build.md) 在临时目录提取并构建上游。以下命令从仓库根目录开始；试验端口不得被其他进程占用。

```bash
mkdir -p /private/tmp/contexture-004-o3l0thdk/host
cp specs/004-web-shell/evidence/embed-spike/package.json specs/004-web-shell/evidence/embed-spike/pnpm-lock.yaml specs/004-web-shell/evidence/embed-spike/index.html specs/004-web-shell/evidence/embed-spike/main.jsx specs/004-web-shell/evidence/embed-spike/style.css specs/004-web-shell/evidence/embed-spike/vite.config.mjs specs/004-web-shell/evidence/embed-spike/transport.js /private/tmp/contexture-004-o3l0thdk/host/
cp -R /private/tmp/contexture-004-o3l0thdk/upstream/web/dist-embed /private/tmp/contexture-004-o3l0thdk/host/embed
pnpm --dir /private/tmp/contexture-004-o3l0thdk/host install --frozen-lockfile
pnpm --dir /private/tmp/contexture-004-o3l0thdk/host build
```

另开两个终端，分别运行（都是隔离夹具，不连接现有平台）：

```bash
node specs/004-web-shell/evidence/embed-spike/transport-server.mjs
```

```bash
pnpm --dir /private/tmp/contexture-004-o3l0thdk/host preview
```

回到仓库根目录运行浏览器检查：

```bash
SPIKE_HOST_DIR=/private/tmp/contexture-004-o3l0thdk/host SPIKE_EVIDENCE_DIR=/private/tmp/contexture-004-o3l0thdk/runtime node specs/004-web-shell/evidence/embed-spike/browser.mjs
```

完成后在两个服务器终端按 Ctrl+C。临时目录允许替换；host 和 upstream 必须仍为同级目录，transport.js 才能导入锁定的源模块。

## 实测结果

宿主生产构建退出码 0；浏览器检查退出码 0。机器可读证据见 [runtime.json](embed-spike/runtime.json)，首轮仅 T003 的记录见 [runtime-primary.json](embed-spike/runtime-primary.json)。

| 检查 | 实际判据 | result |
| --- | --- | --- |
| 挂载 / 深链 | `/workbench/not-a-page` 出现嵌入上游不存在页；scope 根只有一个，React.version 为 18.3.1 | runtime_pass |
| 刷新 | 仍为相同地址和上游不存在页 | runtime_pass |
| 共享 Router | 宿主 Link 切到 `/workbench/settings/general`，上游渲染真实 General 设置内容 | runtime_pass |
| 历史 | 后退回不存在页，再前进恢复设置路径 | runtime_pass |
| 动态模块 | 设置页 lazy chunk 真实执行，无模块加载异常 | runtime_pass |
| CSS | 宿主页头背景保持 rgb(233,237,241)，h1 保持 19px | runtime_pass |
| portal | 打开 Filter sessions 菜单，menu 位于 `.omnigent-app` 内；Escape 可关闭 | runtime_pass |
| 卸载 / 再挂载 | scope 消失后重新出现，路由与内容恢复 | runtime_pass |
| Worker | 宿主二次构建后的 editor / pdf 模块 Worker 均返回 200，构造后没有加载 / 解析错误 | runtime_pass |
| 离线资源 | 阻止非本机页面请求，所有生成静态资源可从本机提供，无外站资源请求 | runtime_pass |
| 浏览器异常 | 未捕获 pageerror 数量为 0 | runtime_pass |

对宿主 source maps 的只读核对只发现一套 `react@18.3.1`、`react-dom@18.3.1`、`react-router@7.18.2` 和对应 DOM facade；没有第二版本的 React / Router。宿主配置另有 dedupe，浏览器同时验证了 hooks 与路由上下文。

## limitations / ownerFeature

- ownerFeature：004；本次证明指定组合下的构建和展示接缝，不是正式集成交付。
- API 使用明确的空列表实验夹具，不提供真实账号、令牌或业务数据；不能视为真实身份 / 会话集成通过。
- Worker 检查只覆盖资源和模块启动；真实编辑、PDF 文档处理、会话文件与执行功能归 007 / 012。
- 宿主构建有大 chunk、部分静态与动态导入重叠警告，未关闭警告或以调高阈值掩盖；后续 007 需按实际交付评估加载预算。
- 初次脚本用了错误夹具形状及不准确的选择器 / 预期文案；按锁定源码校正后复测通过，没有修改产品来迎合脚本。
- 截图保存在临时 evidence 目录，仅作本机查看；可重建配置、断言和 JSON 结果保存于仓库，不纳入上游生成产物。

## Node 22 复核

在独立临时工具目录安装精确 Node 22.20.0，未切换用户系统 Node。使用其 node 二进制直接执行冻结安装的 Vite CLI：

```bash
cd /private/tmp/contexture-004-o3l0thdk/upstream/web
/private/tmp/contexture-004-o3l0thdk/node22/node_modules/.bin/node node_modules/vite/bin/vite.js build --config vite.embed.config.ts
cd /private/tmp/contexture-004-o3l0thdk/host
/private/tmp/contexture-004-o3l0thdk/node22/node_modules/.bin/node node_modules/vite/bin/vite.js build
```

两次构建退出码均为 0（上游 2.56 秒、宿主 2.71 秒）。将 Node 22 的上游产物复制到宿主后重建，并复跑浏览器全部 11 项检查，退出码 0；见 [runtime-node22.json](embed-spike/runtime-node22.json)。测试驱动和静态预览进程使用原有 Node 24，浏览器执行的是 Node 22 构建产物。初次 CLI 误用 `--root` 参数未进入构建，改为在 web 目录执行官方脚本对应命令后成功，不算产品失败或有效红测。
