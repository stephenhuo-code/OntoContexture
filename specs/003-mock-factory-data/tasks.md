---
description: "003 模拟工厂数据集与模拟源系统：任务清单"
---

# Tasks: 003 模拟工厂数据集与模拟源系统

**Input**: `specs/003-mock-factory-data/` 下的 plan.md、spec.md、research.md、data-model.md、contracts/、quickstart.md

**Tests**: 宪法 I 要求测试驱动：每个阶段的测试任务排在实现任务之前，先提交并确认失败，再实现。

**Organization**: 按用户故事分阶段；US1、US2 为 P1，US3、US4 为 P2。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、不依赖未完成的任务）
- **[Story]**: 所属用户故事（US1–US4）
- 路径均相对仓库根目录；生成程序在 `testdata/mockfactory/`，测试在 `testdata/tests/`

## Phase 1: Setup

**Purpose**: 建立 `testdata` 包与测试接入

- [X] T001 创建 `testdata/` 目录结构（`mockfactory/{schema,generate,cases,load}/`、`cases/`、`deploy/{mes,qms}/`、`tests/{unit,integration,cluster}/`）与 `testdata/pyproject.toml`（项目名 `contexture-testdata`，构建方式与 `packages/py-core/pyproject.toml` 一致，依赖 faker、pymysql、asyncpg、pyyaml、jsonschema）
- [X] T002 在根 `pyproject.toml` 中把 `testdata` 加入 uv workspace 成员、`testpaths`（`testdata/tests`）、`[tool.coverage.run] source`（`testdata/mockfactory`）与 isort 的 known-first-party（`mockfactory`），执行 `uv add --package contexture-testdata faker` 锁定 Faker 版本并更新 `uv.lock`
- [X] T003 [P] 在 `testdata/tests/conftest.py` 中提供 Testcontainers 夹具：MySQL 8.4 与 PostgreSQL 17（与 plan 的版本一致，模块级复用），返回连接参数；集成测试标记 `integration`

---

## Phase 2: Foundational

**Purpose**: 所有故事共用的配置、表定义与数据集骨架

**⚠️ CRITICAL**: 完成后才能开始任何用户故事

- [X] T004 [P] 单元测试 `testdata/tests/unit/test_config.py`：基准日固定为 2026-09-30；`--months` 只接受 1–12；同一（种子, 年月）派生的随机流相同，不同年月互不相关；月份列表从最早月到 2026-09
- [X] T005 [P] 单元测试 `testdata/tests/unit/test_schema.py`：三套系统的表清单与 data-model.md 第 3–5 节一致（MES 13 张、QMS 7 张、数仓 8 张）；每张表与每个字段都有中文说明；由表定义生成的 MySQL、PostgreSQL、Doris 建表语句包含字段注释、主键（Doris 为 DUPLICATE / UNIQUE KEY 与 `replication_num=1`）
- [X] T006 实现 `testdata/mockfactory/config.py`：`BASE_DATE`、`DEFAULT_SEED = 20261001`、`Settings(months, seed)` 校验、`month_rng(seed, year, month)`（按月独立随机流）、`months()` 列表
- [X] T007 实现表定义单一来源 `testdata/mockfactory/schema/__init__.py`（`Table`、`Column` 数据类：名称、类型、中文说明、主键）与 `testdata/mockfactory/schema/mes.py`、`qms.py`、`dw.py`（按 data-model.md 第 3–5 节的表与关键字段，补全类型与说明），以及 `ddl(table, dialect)` 生成三种方言的建表语句
- [X] T008 实现数据集容器 `testdata/mockfactory/dataset.py`：按“系统 → 表 → 行”保存生成结果，提供按表追加、按主键排序遍历与行数统计

**Checkpoint**: 配置、表定义与 DDL 可用

---

## Phase 3: User Story 1 - 一条命令得到一家模拟工厂（Priority: P1）🎯 MVP

**Goal**: `make mock-data` 部署模拟 MES、QMS，在三套系统中写入默认规模的数据，并且可复现

**Independent Test**: 已运行 001 环境，执行 `make mock-data`，用数据库客户端核对表、字段说明与行数；两次执行 `checksum` 结果一致

### Tests for User Story 1 ⚠️

- [X] T009 [P] [US1] 单元测试 `testdata/tests/unit/test_master_data.py`：2 条产线、约 20 台设备、每条线 6–8 道工序、每线甲乙两班、约 80 人、6 家供应商、3 家客户；编号符合 data-model.md 第 2 节格式（如 `L2-CNC-03`、`E0123`、`L2-B`）；姓名与公司名由 Faker（`zh_CN`）合成且固定种子下不变
- [X] T010 [P] [US1] 单元测试 `testdata/tests/unit/test_production.py`：每月约 900 个工单与批次、每批按工艺路线逐道报工；报工的设备属于该工序、操作工属于当班班组、开工早于完工且在班次内；投料引用存在的物料批次且在入库之后；每道工序 `good_qty + rework_qty + scrap_qty = input_qty`
- [X] T011 [P] [US1] 单元测试 `testdata/tests/unit/test_quality.py`：检验单对应真实批次、工序或物料批次；实测值在公差带内（正态截断）；NCR 关联真实批次与缺陷码；8D 关联真实 NCR；设备事件只含计划保养与一般报警（不含主轴类预警）
- [X] T012 [P] [US1] 单元测试 `testdata/tests/unit/test_warehouse.py`：DWD 行与 MES、QMS 明细一一对应；DWS 日、月汇总可由 DWD 重算；`fpy_incl_rework =（首次合格 + 返工后合格）÷ 投入`、`fpy_strict = 首次合格 ÷ 投入`，均以终检工序报工为准
- [X] T013 [P] [US1] 单元测试 `testdata/tests/unit/test_reproducible.py`：相同种子与月数两次生成的数据集逐行一致；`months=1` 与 `months=12` 生成的 2026-09 数据完全相同；跨表引用有效率 100%（SC-004）
- [X] T014 [P] [US1] 集成测试 `testdata/tests/integration/test_load.py`：用 T003 的容器执行 `load --target dsn`（1 个月规模，MES、QMS），表与字段注释存在、行数与数据集一致；重复执行得到相同 `checksum`；目标不可连接时退出码 2 且不写数据
- [X] T015 [P] [US1] 单元测试 `testdata/tests/unit/test_doris_load.py`：以记录 SQL 的假连接验证 `load/doris.py` 生成的语句：重建 `mock_dw`、建表（DUPLICATE / UNIQUE KEY、`replication_num=1`、字段注释）、按 1000 行分批 INSERT 且行数与数据集一致、创建只读账号 `mock_dw_reader` 并只授予 `mock_dw` 的 SELECT；写入失败时清空已写入的表（使 `doris.py` 在不跑集群测试的 CI 中也达到覆盖率要求）
- [X] T016 [P] [US1] 集群测试 `testdata/tests/cluster/test_mock_sources.py`（`-m cluster`）：`mock-sources` 中 MES、QMS 可连接；Doris 中存在 `mock_dw` 与只读账号；`load --target local` 后三套系统行数与摘要输出一致

### Implementation for User Story 1

- [X] T017 [P] [US1] 实现主数据生成 `testdata/mockfactory/generate/master.py`：产线、工序（工艺路线）、设备、班组、人员（岗位含操作工、班组长、工艺工程师、质量工程师、检验员、维修工、供应商质量工程师）、物料、供应商、客户、缺陷码、检验项（含公差）
- [X] T018 [US1] 实现生产数据生成 `testdata/mockfactory/generate/production.py`：按月（`month_rng`）生成工单、成品批次、物料批次入库、工序报工、投料（依赖 T017）
- [X] T019 [US1] 实现质量数据与设备事件生成 `testdata/mockfactory/generate/quality.py`：来料、过程、终检检验单与实测值，NCR 与 8D，设备事件；遵守 data-model.md 第 7 节“正常数据的约束”（依赖 T018）
- [X] T020 [US1] 实现数仓生成 `testdata/mockfactory/generate/warehouse.py`：维度表、DWD 明细、DWS 日与月汇总（依赖 T018、T019）
- [X] T021 [US1] 实现生成总入口 `testdata/mockfactory/generate/__init__.py`：`build(settings) -> Dataset`，固定生成与写入顺序
- [X] T022 [P] [US1] 实现 MySQL 写入 `testdata/mockfactory/load/mysql.py`：重建 database `mes`、按 DDL 建表、多行 INSERT（每批约 2000 行）、失败时清空并抛出
- [X] T023 [P] [US1] 实现 PostgreSQL 写入 `testdata/mockfactory/load/postgres.py`：重建 database `qms`、建表与 `COMMENT ON`、asyncpg `copy_records_to_table`、失败时清空
- [X] T024 [P] [US1] 实现 Doris 写入 `testdata/mockfactory/load/doris.py`：重建 database `mock_dw`、建表、批量 INSERT（每批 1000 行）、创建只读账号 `mock_dw_reader`
- [X] T025 [US1] 实现目标解析与本地端口转发 `testdata/mockfactory/load/__init__.py`：`--target dsn`（`--mes`、`--qms`、`--dw`）与 `--target local`（经 `kubectl --context kind-contexture port-forward` 连接 `mock-sources` 中的 MES、QMS 与 `contexture` 中的 Doris，复用 `tools/seed.py` 的做法）；连接前检查就绪与磁盘估算
- [X] T026 [US1] 实现命令行 `testdata/mockfactory/__main__.py` 的 `load` 与 `checksum`（按 contracts/cli.md 的选项、输出与退出码 0–3）
- [X] T027 [P] [US1] 模拟 MES 部署 `testdata/deploy/mes/`：Chart（MySQL 8.4 LTS 官方镜像、锁定补丁版本，StatefulSet + Service + 2Gi 存储卷、约 1Gi 内存，初始化应用账号；密码来自 Secret）与 `tests/smoke.sh`
- [X] T028 [P] [US1] 模拟 QMS 部署 `testdata/deploy/qms/`：CloudNativePG `Cluster` `mock-qms`（PostgreSQL 17.6，1 实例、2Gi 存储卷）与 `tests/smoke.sh`
- [X] T029 [US1] 在 `deploy/helmfile.yaml.gotmpl` 中增加 release `mock-mes`、`mock-qms`（命名空间 `mock-sources`，标签 `group: mock-sources`，local 与 lite 环境，离线模式 `installed: false`）；`tools/up.sh` 生成两者的 Secret 并把 `testdata/deploy/*/tests/smoke.sh` 纳入冒烟测试；确认 `tools/offline_package.py` 与组件检查不收录它们（验收后调整：`make up` 以 `-l 'group!=mock-sources'` 排除模拟库，凭证与冒烟测试改由 `make mock-data` 执行）
- [X] T030 [US1] 在 `Makefile` 中增加 `mock-data`（`MONTHS`、`SEED` 参数）：先执行 `helmfile --kube-context kind-contexture -f deploy/helmfile.yaml.gotmpl -e $(ENV) -l group=mock-sources sync`（可重复执行，环境早于 003 启动时也能补齐模拟库）并等待就绪，再调用 `load --target local`；`tools/ports.sh` 增加 MES `13306`、QMS `15432` 转发及地址说明

**Checkpoint**: US1 可独立演示：一条命令部署并灌入数据，`checksum` 两次一致

---

## Phase 4: User Story 2 - 3 个案例可以按标准答案复现（Priority: P1）

**Goal**: 在 2026-09 注入 C1、C2、C3，标准答案文件可被逐步查询复现

**Independent Test**: `verify-cases` 在 1 个月与 12 个月两种规模下全部通过；按答案文件中的 SQL 手工查询结果一致

### Tests for User Story 2 ⚠️

- [X] T031 [P] [US2] 单元测试 `testdata/tests/unit/test_case_answers.py`：`testdata/cases/*.yaml` 均通过 `specs/003-mock-factory-data/contracts/case-answer.schema.json` 校验（测试读取该 Schema 的副本 `testdata/cases/case-answer.schema.json`，并断言两份一致）
- [X] T032 [P] [US2] 单元测试 `testdata/tests/unit/test_cases.py`：在内存数据集上核对 C1（`L2-CNC-03` 的 09-08 振动预警、09-12 主轴故障停机与维修；09-10—09-11 乙班在该设备精车的 3 个批次；外径偏大且含超差值；09-22 客诉 NCR 与 8D）、C2（供应商 S03 的 1 个毛坯批次投料到 L1 的 6 个工单，其中 4 个终检裂纹、09-18 内部 NCR，2 个尚未发现）、C3（L2 2026-09 两种口径月度一次合格率不同）；案例时段内其他批次、设备无同类异常（FR-009）
- [X] T033 [P] [US2] 集成测试 `testdata/tests/integration/test_verify_cases.py`：在 T003 的容器中加载 1 个月规模，执行 `verify-cases`，C1、C2 全部步骤与 C3 明细口径步骤通过；篡改一条记录后返回退出码 4 并指出差异
- [X] T034 [P] [US2] 集群测试 `testdata/tests/cluster/test_cases_dw.py`（`-m cluster`）：`make mock-data` 后在 `mock_dw` 中执行 C3 汇总口径步骤通过；`MONTHS=1` 重新生成后 `verify-cases` 仍全部通过

### Implementation for User Story 2

- [X] T035 [P] [US2] 实现 C1 注入 `testdata/mockfactory/cases/c1_equipment.py`（固定参数，不随种子变化）
- [X] T036 [P] [US2] 实现 C2 注入 `testdata/mockfactory/cases/c2_material.py`
- [X] T037 [P] [US2] 实现 C3 注入 `testdata/mockfactory/cases/c3_fpy.py`（L2 2026-09 终检返工后合格数量按固定参数注入，DWS 随之重算）
- [X] T038 [US2] 在 `testdata/mockfactory/generate/__init__.py` 中于正常数据之后、数仓生成之前调用三个案例模块（依赖 T035–T037）
- [X] T039 [US2] 编写标准答案 `testdata/cases/C1.yaml`、`C2.yaml`、`C3.yaml`（故事、入口编号、逐步说明、目标系统、SQL、期望列与行）并复制 Schema 到 `testdata/cases/case-answer.schema.json`
- [X] T040 [US2] 实现 `verify-cases` 命令 `testdata/mockfactory/verify.py` 与 `__main__.py` 子命令：按步骤执行只读 SQL、按 `order_by` 排序、按 `tolerance` 比对数值，输出逐步结果，不一致时退出码 4；在 `Makefile` 的 `mock-data` 末尾增加 `verify-cases --target local`

**Checkpoint**: US1 + US2 即完整的 P1：数据可用且案例可复现

---

## Phase 5: User Story 3 - 集成测试按需加载小规模数据（Priority: P2）

**Goal**: 其他特性的集成测试能在 30 秒内加载 1 个月规模数据（含案例）

**Independent Test**: 只启动临时数据库的测试中加载小规模数据并计时

### Tests for User Story 3 ⚠️

- [X] T041 [P] [US3] 集成测试 `testdata/tests/integration/test_fixture_speed.py`：通过公共夹具加载 1 个月规模到空的 MySQL、PostgreSQL 容器，耗时 ≤ 30 秒（不含容器启动），表结构与默认规模一致，3 个案例的入口编号存在

### Implementation for User Story 3

- [X] T042 [US3] 提供可复用的加载函数 `testdata/mockfactory/testing.py`（`load_small(mes_dsn, qms_dsn)`：1 个月规模含 3 个案例，返回数据集）；其他特性直接导入（`mockfactory` 为 workspace 包），不另设夹具、不复制到 `tests/support/`（analyze D1）；用法写入 `testdata/README.md`

**Checkpoint**: 其他特性可直接复用

---

## Phase 6: User Story 4 - 后续特性有一份可依赖的数据说明（Priority: P2）

**Goal**: `testdata/数据说明.md` 与人员名单可直接用于 010、011 等特性

**Independent Test**: 抽查 10 个字段与模拟系统一致；按关联键跨系统关联全部成立

### Tests for User Story 4 ⚠️

- [X] T043 [P] [US4] 单元测试 `testdata/tests/unit/test_docs.py`：由表定义生成的数据说明与仓库中的 `testdata/数据说明.md` 一致；包含工厂组成、编号规则、三套系统的全部表与字段、跨系统关联键
- [X] T044 [P] [US4] 单元测试 `testdata/tests/unit/test_roster.py`：`roster` 输出 CSV 列为工号、姓名、岗位、班组、班次、产线；人数与 MES `employee` 一致；固定种子下内容不变

### Implementation for User Story 4

- [X] T045 [US4] 实现 `testdata/mockfactory/docs.py` 与 `docs`、`roster` 子命令，生成并提交 `testdata/数据说明.md`

**Checkpoint**: 全部用户故事完成

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T046 [P] 编写 `testdata/README.md`：用途、命令、规模、与 001 环境的关系、不进入交付物的说明（MySQL 为 GPL-2.0，见 research R4）
- [X] T047 实测并记录：默认规模部署与生成耗时（SC-001 ≤ 15 分钟）、磁盘占用、1 个月规模加载耗时（SC-005），写入 `specs/003-mock-factory-data/research.md` R10
- [X] T048 编写手动验收文档 `specs/003-mock-factory-data/acceptance.md`（宪法：前置条件、逐步操作、预期结果、与用户故事和成功标准的对应、验收记录），覆盖 quickstart.md 全部步骤与 3 个案例的手工查询，产品负责人 1 小时内可完成（SC-007）
- [X] T049 更新 `docs/Phase1-特性列表与开发计划.md` 中 003 的说明（3 个案例、模拟源系统不进交付包）与 `docs/architecture/platform-architecture.md` 的本地部署说明；运行 `make lint`、`make test`、`make e2e` 全部通过

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup（Phase 1）→ Foundational（Phase 2）→ US1（Phase 3）→ US2（Phase 4）
- US3（Phase 5）依赖 US1 的加载函数（T022、T023、T025）与 US2 的案例（T038）
- US4（Phase 6）只依赖 Foundational 的表定义（T007）与 US1 的主数据（T017），可与 US2 并行
- Polish 在全部故事之后

### Within Each User Story

- 测试先写并确认失败，再实现
- 生成：主数据 → 生产 → 质量与设备事件 →（案例）→ 数仓
- 写入与部署（T022–T024、T027–T028）可与生成并行

### Parallel Opportunities

- T004、T005 并行；T009–T016 并行；T017 与 T022–T024、T027–T028 并行
- T035–T037 并行；T043、T044 并行；US4 与 US2 并行

## Parallel Example: User Story 1

```text
# 先并行写测试：
T009 test_master_data.py  T010 test_production.py  T011 test_quality.py
T012 test_warehouse.py    T013 test_reproducible.py  T014 test_load.py  T016 test_mock_sources.py
# 再并行实现与生成无关的部分：
T017 master.py  T022 mysql.py  T023 postgres.py  T024 doris.py  T027 deploy/mes  T028 deploy/qms
```

## Implementation Strategy

### MVP First

1. Phase 1–2 → Phase 3（US1）：可以一条命令得到可复现的模拟工厂
2. Phase 4（US2）：埋入 3 个案例并可验证，P1 完整
3. **STOP and VALIDATE**：按 quickstart.md 第 1–4 步验证

### Incremental Delivery

- US3：给 010、011、012 等特性的集成测试使用
- US4：010 搭飞书测试租户前完成人员名单
- 最后交付验收文档，由产品负责人手动验收后合并
