# Research: 003 模拟工厂数据集与模拟源系统

## R1 放在哪里、以什么形态交付

- **Decision**：`testdata/` 目录（ADR-0009 已为 003 预留），其中 `testdata/mockfactory/` 是一个 Python 包（uv workspace 成员
  `contexture-testdata`），提供命令行 `python -m mockfactory`；`make mock-data` 调用它。模拟源系统的部署文件放在
  `testdata/deploy/`。
- **Rationale**：它是开发与测试设施，不是服务（宪法 II 不新增服务）；与 `tools/` 分开，避免把测试数据逻辑混进运维脚本。
- **Alternatives**：放进 `tools/`（职责混杂，`tools` 已有组件检查、离线打包等）；做成 Airflow 管线（采集与物化才用管线，生成
  测试数据不需要调度）。

## R2 数据怎么生成

- **Decision**：自写生成程序，字段级的姓名、公司名用 Faker（MIT，`zh_CN`）；表间关系、工厂规则与案例注入用 Python 代码实现。
- **Rationale**：工厂逻辑（工艺路线、设备与工序对应、检验与 NCR 的因果）和案例的跨系统一致性只能按业务规则写成代码；Faker
  只负责“填值”，符合“只用框架自带能力、缺的才自建”。
- **Alternatives**：
  - Snowfakery（BSD-3）：能用 YAML 描述多表关系，但案例注入与跨系统一致性仍要写代码，再引入一套 DSL 得不偿失。
  - SDV：需要真实数据来学习分布，我们没有；且其许可已非开源宽松许可。
  - 现成的模拟 MES / QMS 数据库：未找到可用的开源项目；公开制造数据集（如产线传感器数据）多为单表。

## R3 三套模拟系统用什么数据库

- **Decision**：
  - MES：MySQL 8.4 LTS（官方镜像）。
  - QMS：PostgreSQL 17，用 001 已部署的 CloudNativePG operator 另起一个实例 `mock-qms`。
  - 数仓：001 已部署的 Doris 中新建 database `mock_dw` 与只读账号，放明细层（DWD）与汇总层（DWS）样例表。
- **Rationale**：MySQL 与 PostgreSQL 是国内 MES / QMS 最常见的两类库，正好模拟“客户异构环境”，也是 011 元数据采集要覆盖的
  连接器；数仓用 Doris 不再多起一套重组件（BE 已占 4Gi），客户数仓用 Doris / StarRocks 也很常见。
- **Alternatives**：MariaDB（同为 GPL，无优势）；TiDB（MySQL 兼容、Apache-2.0，但对本地环境过重）；MES 也用 PostgreSQL
  （失去异构，011 少测一类连接器）；数仓单独起一套（资源翻倍）。

## R4 许可与交付边界（对 spec FR-012 的调整）

- **Decision**：模拟源系统是**开发与测试设施，不是交付物**：不放进 `deploy/components/`，不进组件清单检查与离线交付包；只在
  本地（local / lite）环境由 `make mock-data` 按需部署（`make up` 不部署，避免占用约 1.5 GiB 内存；以选择器排除而非设为不安装，以免卸载已有数据），离线模式下跳过。spec FR-012 相应调整。
- **Rationale**：MySQL 社区版为 GPL-2.0，不在宪法 III 的交付许可白名单内；宪法约束的是交付物，测试设施不受此限，但必须明确
  与交付物隔离，避免被组件检查当成交付组件、被离线包打进客户环境。
- **Alternatives**：把 MySQL 列入许可例外（需要 ADR，且没有必要让客户环境带上它）；换用宽松许可的 MySQL 兼容库（见 R3）。

## R5 规模与可复现

- **Decision**：
  - 规模参数为**月数**（1–12，默认 12）；所有日期相对固定基准日 `2026-09-30` 向前生成，与执行当天无关。
  - 每个月使用独立的随机数流（由种子与年月派生），因此改变月数只增减更早的月份，**最后一个月（2026-09）的数据在任何规模下
    完全相同**；3 个案例都放在 2026-09，标准答案因此与规模无关。
  - 种子可配置（默认 `20261001`）；编号按规则顺序生成；写入顺序固定。
  - 提供 `checksum` 命令：按主键排序后对每张表计算摘要，用于证明两次生成逐行一致。
- **Rationale**：满足 FR-005、FR-006、SC-002、SC-003；“按月独立”是让 C3 这类全月统计值在不同规模下不变的最简单办法。
- **Alternatives**：规模参数为“密度系数”（会改变案例月份的统计值，C3 答案随规模变化）；按规模分别维护答案（答案翻倍，容易走样）。

## R6 写入方式

- **Decision**：生成在内存中按月流式产出行，再批量写入：MySQL 用 PyMySQL 多行 INSERT（每批约 2000 行）；PostgreSQL 用 asyncpg
  的 COPY（`copy_records_to_table`）；Doris 用 PyMySQL 经 MySQL 协议批量 INSERT（每批 1000 行：本地 Doris BE 内存上限约 3.2 GB 且空闲已占 2 GB 以上，每批 5000 行会触发 MEM_LIMIT_EXCEEDED）。本地环境经
  `kubectl port-forward` 连接（与 `tools/seed.py` 一致）。
- **Rationale**：三个驱动中 PyMySQL、asyncpg 已在依赖锁定中，无需新增；默认规模合计百万行级，批量 INSERT / COPY 足以在
  SC-001 的时间内完成。Doris Stream Load 需要从本机直连 BE，经 port-forward 不可达，故不用。
- **Alternatives**：MySQL `LOAD DATA LOCAL INFILE`（需开启服务器选项，收益有限）；在集群内以 Job 运行生成器（多一个镜像，
  本地开发不需要）。

## R7 案例注入与标准答案

- **Decision**：
  - 正常数据由规则约束“不会出现案例类异常”：关键尺寸在公差带内按正态分布截断生成；来料硬度在合格区间内；设备事件只有
    计划保养与一般报警，不出现主轴类预警；NCR 的缺陷码与责任工序避开案例组合。
  - 每个案例是一个独立模块，在 2026-09 的正常数据之上按固定参数注入记录（不随种子变化）。
  - 标准答案写在 `testdata/cases/C1.yaml` 等文件中（人工维护的“金标准”），包含故事、入口编号、逐步查询（附 SQL）与期望结果；
    测试在生成后的数据上执行这些 SQL 并逐项比对，保证答案与数据不走样（FR-008）。
- **Rationale**：金标准文件独立于生成代码，才能真正检验生成结果；把 SQL 写进答案文件，验收人员也能直接照着查。
- **Alternatives**：从生成结果反向导出答案（答案永远“正确”，失去检验意义）。

## R8 测试策略（宪法 I）

- **Decision**：
  - 单元测试：工厂规则（引用完整、时间先后、班次一致）、按月独立与可复现、案例注入后的内存数据满足标准答案、DWS 可由 DWD 重算。
  - 集成测试（Testcontainers）：MySQL 8.4 与 PostgreSQL 17 容器加载 1 个月规模（含 3 个案例），30 秒内完成，并执行 C1、C2 与
    C3 明细口径的答案 SQL。
  - 集群测试（`-m cluster`，需 `make up` 与 `make mock-data`）：模拟源系统冒烟测试；Doris `mock_dw` 中执行 C3 的汇总口径 SQL。
  - 数据说明一致性测试：由表定义重新生成的 `数据说明.md` 与仓库中的文件一致。
- **Rationale**：Doris 没有轻量容器可用于常规集成测试，数仓部分在集群测试中验证，其计算逻辑在单元测试中覆盖。

## R9 数据说明与人员名单

- **Decision**：表与字段定义（含中文说明）在代码中只写一处，由它生成三套库的建表语句（字段 COMMENT）与 `testdata/数据说明.md`；
  `roster` 命令导出人员与班组名单（CSV），010 搭飞书测试租户时直接使用。
- **Rationale**：单一来源，避免文档与库结构不一致（SC-006）。

## R10 资源与时间预算

- **Decision**：MySQL 约 1Gi 内存、PostgreSQL 512Mi，各 2Gi 存储卷；目标为默认规模生成与写入 ≤ 10 分钟、部署 ≤ 5 分钟
  （合计满足 SC-001 的 15 分钟）。
- **实测（2026-10-23，Apple Silicon 开发机、001 本地环境）**：
  - 生成：默认 12 个月 1,041,352 行，约 2 秒；1 个月 85,770 行，约 0.2 秒。
  - 首次部署模拟 MES、QMS：约 2 分钟（含拉取 MySQL 镜像）；已部署时同步约 20 秒（含冒烟测试等待）。
  - 写入默认规模：MES + QMS 约 45 秒，数仓约 2 分半（Doris 每批 1000 行，见 R6）；`make mock-data` 端到端约 3 分钟。
  - 集成测试载入 1 个月规模（MySQL、PostgreSQL 容器）：约 1 秒（不含容器启动约 9 秒），满足 SC-005。
  - 磁盘：MES 约 50 MB、QMS 约 58 MB，Doris 为压缩列存（更小），远低于原估计的 1–2 GB。
