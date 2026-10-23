# 手动验收：003 模拟工厂数据集与模拟源系统

- 依据：宪法 v1.7.0“每个特性交付手动验收文档”；spec 的用户故事 1–4 与 SC-001–SC-007
- 验收人：产品负责人（@stephenhuo-code）
- 预计用时：约 50 分钟（第 1 部分 15 分钟、第 2 部分 25 分钟、第 3 部分 10 分钟），不需要读代码
- 每一步做完，在第 5 节记录表中填“通过 / 不通过 / 备注”。不通过的步骤请记下现象（截图或复制输出），我修复后复验。

## 0. 前置条件

- 001 的本地环境在运行：`kubectl --context kind-contexture -n contexture get pods` 基本都是 Running / Completed。
  Docker Desktop 重启后的恢复方法见 001 验收文档第 0.1 节。
- 在仓库根目录执行以下命令。下文用到三个查询入口（不需要另装数据库客户端，直接进入集群里的数据库）：

```bash
# 模拟 MES（MySQL）
kubectl --context kind-contexture -n mock-sources exec -it mock-mes-0 -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" mes'
# 模拟 QMS（PostgreSQL）
kubectl --context kind-contexture -n mock-sources exec -it mock-qms-1 -c postgres -- psql qms
# 模拟数仓（Doris，database mock_dw）
DPW=$(kubectl --context kind-contexture -n contexture get secret doris-root -o jsonpath='{.data.password}' | base64 -d)
kubectl --context kind-contexture -n contexture exec -it doris-fe-0 -c fe -- mysql -h127.0.0.1 -P9030 -uroot -p"$DPW" mock_dw
```

> 这三个入口要在第 1.1 步之后才有数据。退出：MySQL / Doris 输入 `exit`，PostgreSQL 输入 `\q`。

## 1. 一条命令得到一家模拟工厂（用户故事 1，SC-001 / SC-002 / SC-004）

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 1.1 | `time make mock-data` | 15 分钟内结束（实测约 3 分钟；首次部署多约 2 分钟）。输出 `[mes]`、`[qms]`、`[dw]` 三段，每张表的行数，最后“合计 1041352 行”；接着 `verify-cases` 打印 C1–C3 共 15 步“通过”，末行“合计 15 步：通过 15，失败 0，跳过 0” |
| 1.2 | `uv run python -m mockfactory checksum --target local > /tmp/a.txt`，再执行 `make mock-data`，再执行 `uv run python -m mockfactory checksum --target local > /tmp/b.txt`，最后 `diff /tmp/a.txt /tmp/b.txt && echo 一致` | 打印“一致”：两次生成的 28 张表逐行相同（摘要文件每行：系统、表名、行数、摘要） |
| 1.3 | 进入 MES，执行 `SHOW FULL COLUMNS FROM operation_report;` | 每个字段的 Comment 列都有中文说明（如 `good_qty` 为“首次合格数量”） |
| 1.4 | 进入 QMS，执行 `\d+ ncr` | Description 列每个字段都有中文说明 |
| 1.5 | 进入数仓，执行 `SHOW TABLES;` | 8 张表：`dim_equipment`、`dim_line`、`dim_product`、`dwd_inspection_value`、`dwd_ncr`、`dwd_operation_report`、`dws_line_daily_quality`、`dws_line_monthly_quality` |
| 1.6 | 另开终端执行 `make ports` | 地址清单中有“模拟 MES（MySQL）localhost:13306”与“模拟 QMS（PostgreSQL）localhost:15432”，并显示各自密码；可用任意数据库客户端连接（Ctrl+C 结束） |

## 2. 3 个案例按标准答案复现（用户故事 2，SC-003）

标准答案在 `testdata/cases/C1.yaml`、`C2.yaml`、`C3.yaml`：每个文件先讲故事，再列出逐步查询（`sql`）与期望结果（`expected`）。
请打开文件，把每一步的 `sql` 粘贴到对应系统（`system: mes` / `qms` / `dw`）中执行，核对结果与 `expected.rows` 一致。

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 2.1 | 读 `C1.yaml` 的 `story`，按 6 个步骤逐一查询 | 从客诉 `NCR-2609-0901` 追到批次 `B260911-L2-03` → 设备 `L2-CNC-03`、乙班操作工 `E0047` → 同班次同设备的 3 个批次 → 10 个超差的外径实测值 → 设备 09-08 的振动预警（处理人为空）、09-12 的停机与维修 → 班组长 `E0046`；每步结果与文件一致 |
| 2.2 | 读 `C2.yaml`，按 6 个步骤逐一查询 | 从 `NCR-2609-0902` 追到毛坯批次 `ML260902-901`（供应商 S03）→ 同一物料批次流向的 6 个工单 → 其中 4 批终检有裂纹、2 批“合格”（尚未发现问题）→ 来料硬度 28.3–28.9（下限 28）；与文件一致 |
| 2.3 | 读 `C3.yaml`，按 3 个步骤查询（第 3 步在数仓） | 2 号线 2026-09 终检投入 60000、首次合格 59213、返工后合格 720、报废 67；帆软口径 0.9989、严格口径 0.9869；数仓月汇总与明细计算一致 |
| 2.4 | 在 MES 中执行 `SELECT COUNT(*) FROM operation_report WHERE equip_code = 'L2-CNC-03' AND started_at >= '2026-09-11' AND started_at < '2026-09-12 09:30:00';` | 结果为 3：案例时段内这台设备只有案例的 3 个批次，没有其他记录干扰判断 |
| 2.5 | `make mock-data MONTHS=1` | 合计 85770 行；`verify-cases` 仍是 15 步全部通过（2026-09 的数据与案例在任何规模下相同） |
| 2.6 | `make mock-data` | 恢复默认的 12 个月数据，供后续特性使用 |

## 3. 集成测试与数据说明（用户故事 3、4，SC-005 / SC-006 / SC-007）

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 3.1 | `uv run pytest testdata/tests -q` | 全部通过（会启动临时的 MySQL 与 PostgreSQL 容器）；其中“1 个月规模 30 秒内载入”的测试实测约 1 秒 |
| 3.2 | 打开 `testdata/数据说明.md`，任选 10 个字段（不同表），在对应系统中用 1.3 / 1.4 的命令核对 | 字段名与中文说明一致；文档含工厂组成、编号规则、跨系统关联键、案例、全部表与字段、人员名单 |
| 3.3 | `uv run python -m mockfactory roster --out /tmp/roster.csv`，打开该文件 | 表头为“工号,姓名,岗位,班组,班次,产线”，共 80 人；`E0047` 一行为“操作工、L2-B、夜班、L2” |
| 3.4 | 回顾本次验收用时 | 1 小时以内（SC-007） |

## 4. 由我执行、需要你知晓的验证结果

| 项 | 结果 |
| --- | --- |
| 单元与集成测试 | `make test`：174 个通过；总覆盖率 87.5%（`mockfactory` 各模块 63%–100%，本地端口转发部分由集群测试覆盖） |
| 集群测试 | `pytest -m cluster testdata/tests/cluster`：3 个通过（12 个月与 1 个月两种规模下 `verify-cases` 15 步全部通过，含数仓中的 C3 汇总口径；只读账号 `mock_dw_reader` 可查询、不能删改） |
| 整体部署 | `make up`：通过，全部组件冒烟测试通过。验收后按负责人要求调整为 `make up` 不部署模拟库（由 `make mock-data` 按需部署），调整后复验见下行 |
| 调整后复验 | `make up`（2026-10-23）：通过，17 个平台组件冒烟测试通过；不再部署也不改动模拟库（`mock-mes`、`mock-qms` 的版本号不变，数据保留）。顺带修复 001 的 `up.sh` 在端口转发已退出时 `kill` 失败导致整体退出的问题 |
| 端到端 | `make e2e`（2026-10-23）：15 个集群测试与 3 个浏览器测试全部通过（已包含 `testdata/tests/cluster`） |
| 环境原因的失败 | 第一次运行 `make e2e` 时，001 的追踪测试失败：Langfuse 自带的 ClickHouse 连续运行 2 天后内存超过上限（常驻 1.36 GiB，上限 1.13 GiB），查询报错。与 003 无关；重启 `clickhouse-0` 后重跑全部通过。长期处理（调大 ClickHouse 内存上限）作为 001 的遗留问题另行安排 |
| 代码检查 | `make lint`：通过（ruff、pyright 0 错误、eslint、prettier） |
| 离线安装 | 离线模式下 `mock-mes`、`mock-qms` 不安装，且不需要 `testdata/` 目录 |
| 耗时与磁盘 | 见 `research.md` R10：生成约 2 秒，写入约 3 分钟；MES 约 50 MB、QMS 约 58 MB |

## 5. 验收记录

| 部分 | 步骤 | 日期 | 验收人 | 结果 | 发现的问题 |
| --- | --- | --- | --- | --- | --- |
| 1 一条命令 | 1.1–1.6 | 2026-10-23 | @stephenhuo-code | 通过 | 无；1.1 中 `load` 写入约 3 分钟期间没有进度输出（不属于验收缺陷，后续可加进度提示） |
| 2 案例 | 2.1–2.4 | 2026-10-23 | Claude（执行）／@stephenhuo-code（确认） | 通过 | 无；3 个案例 15 步逐条查询，结果与标准答案一致 |
|  | 2.5–2.6 | 2026-10-23 | @stephenhuo-code | 通过 | 无 |
| 3 测试与数据说明 | 3.1–3.4 | 2026-10-23 | @stephenhuo-code | 通过 | 无 |

**结论**：003 手动验收通过（2026-10-23，@stephenhuo-code），可按宪法合并到 main。

## 6. 与用户故事、成功标准的对应

| 成功标准 | 用户故事 | 验收步骤 |
| --- | --- | --- |
| SC-001 一条命令 15 分钟内完成 | US1 | 1.1 |
| SC-002 相同参数两次生成逐行一致 | US1 | 1.2 |
| SC-003 案例答案在两种规模下 100% 复现 | US2 | 2.1–2.3、2.5 |
| SC-004 关联键有效率 100% | US1 | 第 4 节（单元测试）、2.1–2.2 的跨系统查询 |
| SC-005 小规模加载 ≤ 30 秒 | US3 | 3.1 |
| SC-006 中文说明全覆盖、抽查 10 个字段一致 | US4 | 1.3–1.5、3.2 |
| SC-007 1 小时内完成验收 | 全部 | 3.4 |

## 7. 已知限制（不影响本次验收）

- 模拟源系统是开发测试设施，不进组件清单与离线安装包（spec FR-012 在 plan 阶段调整，见 research R4）。
- 不模拟 ERP、设备时序数据与脏数据；飞书测试租户在 010、20 个追溯案例在 019、帆软 SQL 样例在 024 交付。
- 本地 Doris BE 内存紧张，数仓按每批 1000 行写入（research R6）；阿里云测试环境资源充足时可调大。
- 集群测试会把本地数据改为 1 个月规模；验收前请以 2.6 的 `make mock-data` 恢复 12 个月。
