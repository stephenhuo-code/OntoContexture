# testdata/：模拟工厂数据集与模拟源系统（003）

一家假的、但像真的汽车零部件工厂：模拟 MES（MySQL）、模拟 QMS（PostgreSQL）与模拟数仓（Doris 的 `mock_dw` 库），
数据由 `mockfactory` 生成，并埋入 3 个带标准答案的案例。全部为合成数据。规格与设计见 `specs/003-mock-factory-data/`。

## 常用命令

```bash
make mock-data                      # 部署模拟 MES、QMS（make up 不部署它们），生成并写入 12 个月数据（约 104 万行），核对 3 个案例
make mock-data MONTHS=1 SEED=7      # 规模（1–12 个月）与种子；2026-09 的数据与 3 个案例在任何规模下都相同
make ports                          # 转发 MES localhost:13306、QMS localhost:15432，并打印密码

uv run python -m mockfactory verify-cases --target local   # 按 cases/*.yaml 核对案例
uv run python -m mockfactory checksum --target local       # 逐表摘要，两次生成应一致
uv run python -m mockfactory docs                          # 重新生成 数据说明.md
uv run python -m mockfactory roster --out roster.csv       # 人员与班组名单（010 搭飞书测试租户用）
```

命令的选项与退出码见 `specs/003-mock-factory-data/contracts/cli.md`。

## 目录

| 路径 | 内容 |
| --- | --- |
| `mockfactory/schema/` | 三套系统的表与字段定义（中文说明的唯一来源），生成建表语句与 `数据说明.md` |
| `mockfactory/generate/` | 主数据、生产、质量与设备事件、数仓；按月生成，每月独立随机流 |
| `mockfactory/cases/` | C1 设备故障追溯、C2 来料不良追溯、C3 一次合格率口径分歧，注入 2026-09 |
| `mockfactory/load/` | 写入 MySQL、PostgreSQL、Doris；`local` 目标经端口转发连接本地集群 |
| `cases/` | 标准答案（金标准，人工维护）：故事、入口编号、逐步查询 SQL 与期望结果 |
| `cases/Agent测试案例.md` | 给 Agent 测试人员：每个案例的用户场景、典型提问与追问、排查链路与调用的数据、评分要点 |
| `deploy/` | 模拟 MES、QMS 的 Chart 与冒烟测试，凭证脚本 `secrets.sh` |
| `数据说明.md` | 工厂组成、编号规则、跨系统关联键、全部表与字段、人员名单（生成，勿手工编辑） |

## 在其他特性的集成测试中使用

```python
from mockfactory.testing import load_small

ds = load_small(mysql_dsn, postgres_dsn)  # 1 个月规模（含 3 个案例），约 1 秒
```

`mysql_dsn` 形如 `mysql://root:密码@主机:端口`，`postgres_dsn` 形如 `postgresql://postgres:密码@主机:端口/postgres`
（通常来自 Testcontainers）；载入后 MES 在 database `mes`，QMS 在 database `qms`。

## 不进入交付物

模拟源系统只用于本地开发与测试：不放在 `deploy/components/`，不进组件清单检查与离线安装包，离线安装时不部署。
MySQL 社区版为 GPL-2.0，不在交付许可白名单内（`specs/003-mock-factory-data/research.md` R4）。
