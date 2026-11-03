# 004 实施基线

记录日期：2026-11-02。当前分支 `docs/plan-progress-003`；工作区已有规划、ADR、契约和生成类型改动，实施保留这些改动，不自动提交或切换分支。

## 范围与开工确认

- 负责人在本次会话确认“确定没有问题，开工吧”，允许在安全 / 许可清单未勾选的状态下继续实施。清单标记保持原状（requirements 16/16；security-license 0/22），不代填评审记录。
- 004 只交付外壳、身份边界、设计系统和兼容性报告；正式采集、搜索、Agent、审批、执行分别由后续特性承担。
- 退出基线：只删除当前织境 BFF 会话、过期 Cookie、清前端缓存，不调用 IdP logout。基线代码仍调用上游 logout，后续须先写失败测试再修改，产品决策不等于代码已经实现。
- 原型仅为设计输入，不复制原型或上游 UI 实现代码。

## 固定输入

| 输入 | 命令 | 实际结果 |
| --- | --- | --- |
| HTML 原型 | `shasum -a 256 specs/004-web-shell/prototype/index.html` | `28ff26f9894590fcf1151516b18f6a7814218b417a376a2d927ed159f077840d`，与 spec 一致 |
| Omnigent | `git -C third_party/omnigent/src rev-parse HEAD` | `a8676d23e88df7918f4f8ef1c7c4e3186e710354` |
| 上游工作区 | `git -C third_party/omnigent/src status --short` | 空，无源码修改 |
| Node | `node --version` | `v24.21.0`，与计划 Node 22 不同，隔离试验需记录实际版本，不能冒称已验证 22 |
| pnpm | `pnpm --version` | `11.20.0`；上游 packageManager 为 `11.15.1`，安装时核对 |
| Python | `.venv/bin/python --version` | `3.12.13` |
| uv | `uv --version` | `0.12.0` |

## 已执行的既有测试

全部命令从仓库根目录执行，退出码均为 0。

```bash
pnpm --filter @contexture/web test
pnpm --filter @contexture/web build
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest services/bff/tests/unit services/bff/tests/contract packages/py-core/tests/test_auth.py -q -o addopts='--import-mode=importlib' -p no:cacheprovider
```

- Web：1 个文件，4 个测试通过；Vitest 5.0.5。
- BFF 单元 / 契约与公共鉴权：42 个测试通过（2.11 秒）。
- Web：TypeScript 检查与 Vite 8.3.4 生产构建通过（97 个模块）。
- 尚未执行全量 Python 测试、真实身份 / PostgreSQL 集成、集群 E2E、覆盖率或最终门禁；上述结果不能代表 004 已实现或验收。

## 兼容性试验位置

从锁定提交用 `git archive` 提取到 `/private/tmp/contexture-004-o3l0thdk/upstream`，不修改子仓库。临时目录不作为长期证据，后续附件须保存重建配置、命令、版本与实际结果。

## 项目忽略配置核对

Git 工作区与 Node / Python / Docker 配置已核对。现有规则覆盖 node_modules、dist、build、Python 虚拟环境及 Playwright 产物；补入 .env / .env.*（保留显式 example）、日志与 coverage，Docker / ESLint / Prettier 同步排除生成产物。包均 private，不生成发布用 .npmignore；未发现自有 Terraform 工程。已有 Helm chart 为本地配置部署输入，本次不发布 Chart 包、也不在其目录生成构建物，未新增无实际用途的根 .helmignore。
