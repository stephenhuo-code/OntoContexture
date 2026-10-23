# 命令行契约：mockfactory

入口：`uv run python -m mockfactory <命令> [选项]`；常用方式经 `make` 调用。

## 公共选项

| 选项 | 默认 | 说明 |
| --- | --- | --- |
| `--months N` | `12` | 规模：基准日 2026-09-30 之前的月数，1–12 |
| `--seed N` | `20261001` | 随机种子；相同种子与月数生成的数据逐行一致 |

## 命令

| 命令 | 作用 | 输出 | 退出码 |
| --- | --- | --- | --- |
| `load --target local` | 连接本地环境的三套模拟系统（自动端口转发），重建表并写入数据 | 各系统连接方式、每张表行数、耗时 | 0 成功；1 参数错误；2 目标系统未就绪；3 写入失败（已回滚为空库） |
| `load --target dsn --mes <dsn> --qms <dsn> [--dw <dsn>]` | 写入指定数据库（集成测试用 Testcontainers 的地址） | 同上 | 同上 |
| `checksum --target ...` | 按主键排序后计算每张表的摘要 | 每张表一行：系统、表名、行数、摘要 | 0 |
| `verify-cases --target ...` | 执行 `testdata/cases/*.yaml` 中的查询并与期望结果比对 | 每个案例、每一步的通过 / 失败及差异 | 0 全部通过；4 有不一致 |
| `docs` | 由表定义重新生成 `testdata/数据说明.md` | 文件路径 | 0 |
| `roster [--out 文件]` | 导出人员与班组名单（CSV：工号、姓名、岗位、班组、班次、产线） | CSV | 0 |

## make 目标

| 目标 | 等价于 |
| --- | --- |
| `make mock-data [MONTHS=12] [SEED=20261001]` | 先同步部署 `mock-mes`、`mock-qms`（helmfile 标签 `group=mock-sources`，可重复执行），再 `load --target local`，最后 `verify-cases --target local` |

## 约定

- 重建：`load` 先删除并重建本特性管理的 database（`mes`、`qms`、`mock_dw`），不触碰其他库。
- 开始前检查目标系统可连接，并估算磁盘需求；不满足时退出码 2，不写任何数据。
- 写入失败时清空已写入的表并以退出码 3 结束，再次执行即可从头重建。
