# T002：锁定 Omnigent 官方嵌入构建

2026-11-02，`result = runtime_pass`（仅官方构建；宿主运行另见后续证据）。

## 输入与实际工具链

- upstreamCommit：`a8676d23e88df7918f4f8ef1c7c4e3186e710354`，v0.18.0。
- 隔离副本：`/private/tmp/contexture-004-o3l0thdk/upstream`，由 `git archive` 提取，不修改子仓库。
- Node：24.21.0（计划基线 22 的运行未验证）；pnpm：上游 packageManager 自动选择并验证签名的 11.15.1。
- React / ReactDOM 18.3.1、react-router-dom / react-router 7.18.2、Vite 8.1.0、Tailwind 4.3.1、Radix 1.6.3、Query 5.101.2。
- 上游锁文件 SHA-256：`369e525b9445218ee60abc349ad9d68e562afb949aac517cd1e4aee253b10a4b`。

## procedure

从仓库根目录选择一个新的临时目录（以下路径仅为本次实测位置）：

```bash
mkdir -p /private/tmp/contexture-004-o3l0thdk/upstream
git -C third_party/omnigent/src archive --format=tar --output=/private/tmp/contexture-004-o3l0thdk/upstream.tar a8676d23e88df7918f4f8ef1c7c4e3186e710354
tar -xf /private/tmp/contexture-004-o3l0thdk/upstream.tar -C /private/tmp/contexture-004-o3l0thdk/upstream
cd /private/tmp/contexture-004-o3l0thdk/upstream
pnpm --filter web... install --frozen-lockfile
pnpm --dir web build:embed
```

安装退出码 0，1316 个包；构建退出码 0，7218 模块，构建报告耗时 2.77 秒。
初次在受限环境启动 pnpm 时无法访问注册表完成包管理器签名验证；获得联网权限后成功重试。
没有关闭签名校验、放宽冻结锁文件或修改上游依赖。

## 产物

| 产物 | 大小（bytes） | SHA-256 / 数量 |
| --- | ---: | --- |
| `web/dist-embed/omnigent-embed.js` | 3770872 | `9bf7d151c7c5356ef07c12cae5eb298d838e77a3c8e1ecb8c2c45fe1ffb5f55f` |
| `web/dist-embed/omnigent-embed.css` | 2274688 | `82b5fef40b6d23b611db8063a70ee7713fa399524a6d42e80e02997351632cea` |
| `chunks/*.js` | — | 543 个 |
| `assets/editor.worker-Dd95eztV.js` | 280085 | 已生成 |
| `assets/pdf.worker.min-8IBUfuck.js` | 1292443 | 已生成 |

全部输出（含 source maps）100065771 bytes；不纳入主仓库。官方构建保留动态导入、共享 React / Router 的 bare imports，CSS 有作用域处理。

## evidenceLocation、限制与责任

- 最小宿主配置及锁文件保存于 [embed-spike/](embed-spike/)，只含本次实验代码，不含上游源码、node_modules 或构建产物。
- 重建宿主时把上述 `web/dist-embed` 复制到临时宿主的 `embed/`，再按其 package.json 构建；宿主计划使用 Vite 8.3.4，不能把本次上游 8.1.0 构建当作宿主已经通过。
- CSS 构建有 `::highlight` 识别警告；未将警告关闭或算成运行错误。运行样式、portal 和 Worker 必须继续验证。
- ownerFeature：004。正式服务、真实身份、Agent 对话不属于本次构建验证，归 007。

## Node 22 复核

在独立临时工具目录安装精确 Node 22.20.0，未切换用户系统 Node。使用其 node 二进制直接执行冻结安装的 Vite CLI：

```bash
cd /private/tmp/contexture-004-o3l0thdk/upstream/web
/private/tmp/contexture-004-o3l0thdk/node22/node_modules/.bin/node node_modules/vite/bin/vite.js build --config vite.embed.config.ts
cd /private/tmp/contexture-004-o3l0thdk/host
/private/tmp/contexture-004-o3l0thdk/node22/node_modules/.bin/node node_modules/vite/bin/vite.js build
```

两次构建退出码均为 0（上游 2.56 秒、宿主 2.71 秒）。将 Node 22 的上游产物复制到宿主后重建，并复跑浏览器全部 11 项检查，退出码 0；见 [runtime-node22.json](embed-spike/runtime-node22.json)。测试驱动和静态预览进程使用原有 Node 24，浏览器执行的是 Node 22 构建产物。初次 CLI 误用 `--root` 参数未进入构建，改为在 web 目录执行官方脚本对应命令后成功，不算产品失败或有效红测。
