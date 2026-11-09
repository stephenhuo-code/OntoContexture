# 006 资产搜索与摘要：验收文档（草稿，实施中持续补充）

> 本文件在实施过程中逐步补充；T070 时整理为正式验收文档。

## 环境前置（D11，T001–T002）

| 项 | 结论 |
| --- | --- |
| 排查时间 | 2026-11-09 15:07 |
| 集群 | kind-contexture，环境 `lite`（OpenSearch 堆 384m） |
| 现象 | `opensearch-cluster-master-0` 重启 321 次，`lastState.terminated.reason=OOMKilled`，exitCode 137 |
| 原因 | lite 的容器内存上限 1Gi，只够堆本身；JVM 堆外直接内存默认等于堆大小，再加元空间、代码缓存、线程栈等原生开销，超出上限后被 cgroup 杀掉 |
| 处理 | 只改配置：`deploy/components/opensearch/values/lite.yaml` 的内存上限 1Gi → 1280Mi（堆不变）；新增 `deploy/components/opensearch/tests/test_values.py`，要求上限不低于「2 × 堆 + 512Mi」 |
| 应用 | `helmfile -e lite -l component=opensearch sync`，15:11 完成滚动 |
| 闸门 | 15:11–15:21 每分钟观察一次，重启次数始终为 0；集群健康 `yellow`（单节点副本分片未分配，属预期） |

## 开工基线（T003）

| 检查 | 结果 |
| --- | --- |
| `make test` | 405 passed，覆盖率 89.42% |
| `pnpm --filter @contexture/web test` | 13 个文件，102 passed |
| `make lint` | 失败 2 项，均来自本次新增的 `test_values.py` 类型标注，已在提交 be5e23c 修正；不是 005 遗留问题 |

## 开发态元数据导入（T004–T010）

- `make dev-metadata` 首次运行：新建 50 个实体（2 个分类、3 个标签、2 个业务域、1 个术语表、3 个术语、3 个服务、3 个库、4 个 Schema、29 张表）。
- 第二次运行：新建 0，更新 0，未变化 50。
- 实测中发现并修复两个问题：
  - 响应头经集群网络返回时为小写 `x-openmetadata-change`，原实现按大小写敏感读取，导致第二次运行误报「更新 50」；
  - OM 不允许删除仍有标签的分类（`HTTP 400 classification is not empty`），即使带 `recursive=true`；撤除改为先删标签再删分类。
- 分类实体没有 `tags` 字段，无法贴开发态标识；改用描述前缀 `[织境开发态测试元数据]` 判断归属（research R12 的补充，T069 回写）。
- 「写入后短暂搜不到」观察：撤除后重新导入，导入完成后第一次查询即可搜到全部 29 张表（0.0s）。
