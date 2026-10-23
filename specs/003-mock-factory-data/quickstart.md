# Quickstart: 003 模拟工厂数据集与模拟源系统

验证本特性端到端可用。命令与选项见 [contracts/cli.md](contracts/cli.md)，表与案例见 [data-model.md](data-model.md)。

## 前置条件

- 001 的本地环境已运行（`make up`）。模拟 MES、QMS 部署在命名空间 `mock-sources`（`make up` 不部署它们，由 `make mock-data` 按需部署），数仓库在已有 Doris 中。

## 1. 生成默认规模数据并核对案例

```bash
time make mock-data
```

期望：15 分钟内结束（含模拟 MES、QMS 的部署）；输出三套系统的连接方式与每张表行数（合计 1,041,352 行）；
最后 `verify-cases` 报告 C1、C2、C3 全部步骤通过。

## 2. 可复现

```bash
uv run python -m mockfactory checksum --target local > /tmp/a.txt
make mock-data
uv run python -m mockfactory checksum --target local > /tmp/b.txt
diff /tmp/a.txt /tmp/b.txt && echo 一致
```

## 3. 规模变化不影响案例

```bash
make mock-data MONTHS=1
```

期望：总行数 85,770；`verify-cases` 仍全部通过（案例与 2026-09 的数据与默认规模相同）。

## 4. 用数据库客户端查看

`make ports` 增加的转发：MES `localhost:13306`、QMS `localhost:15432`；数仓经 Doris `localhost:9030`（database `mock_dw`）。
按 `testdata/cases/C1.yaml` 中的 SQL 逐步查询，结果与文件中的期望一致；表与字段带中文说明。

## 5. 集成测试

```bash
uv run pytest testdata/tests
```

期望：Testcontainers 启动 MySQL 与 PostgreSQL，加载 1 个月规模（30 秒内），C1、C2 与 C3 明细口径的答案查询通过。

## 6. 数据说明与人员名单

```bash
uv run python -m mockfactory docs   # 与仓库中的 testdata/数据说明.md 无差异
uv run python -m mockfactory roster --out /tmp/roster.csv
```
