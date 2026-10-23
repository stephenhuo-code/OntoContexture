# Implementation Plan: 003 模拟工厂数据集与模拟源系统

**Branch**: `003-mock-factory-data` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-mock-factory-data/spec.md`

## Summary

在 `testdata/` 下交付一个生成程序 `mockfactory` 和两套模拟源系统：MES（MySQL）、QMS（PostgreSQL，复用 CloudNativePG），数仓放在已有
Doris 的 `mock_dw` 库。一条命令 `make mock-data` 按“月数 + 种子”生成一家汽车零部件厂约一年的生产与质量数据（默认约 104 万行），
写入三套系统，并核对 3 个案例（C1 设备故障追溯、C2 来料不良追溯、C3 一次合格率口径分歧）的标准答案。生成逻辑自写，Faker 只填姓名与
公司名；每月独立随机流，使案例所在的 2026-09 在任何规模下都相同。模拟源系统是测试设施，不进组件清单与离线交付包。决策依据见
[research.md](research.md)。

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Faker（MIT，新增，`zh_CN`）；PyMySQL（MIT）与 asyncpg（Apache-2.0），均已在依赖锁定中；PyYAML、jsonschema
（已有，用于读取与校验案例答案文件）

**Storage**: MySQL 8.4 LTS（模拟 MES，database `mes`）；PostgreSQL 17（模拟 QMS，CloudNativePG 实例 `mock-qms`，database `qms`）；
Doris 4.1.5（已有，database `mock_dw`）

**Testing**: pytest；Testcontainers（MySQL 8.4、PostgreSQL 17）；集群测试 `-m cluster`（Doris 与已部署的模拟源系统）；覆盖率 ≥ 80%

**Target Platform**: 001 的本地 kind 环境（local / lite）；不部署到阿里云测试环境与客户环境

**Project Type**: 命令行工具 + 测试数据 + 两个本地部署的模拟数据库

**Performance Goals**: 默认规模生成并写入 ≤ 10 分钟，部署 ≤ 5 分钟（SC-001 合计 15 分钟）；1 个月规模载入测试容器 ≤ 30 秒（SC-005）

**Constraints**: 逐行可复现（固定基准日 2026-09-30、可配置种子）；数据全部合成；本地资源可承受（两个数据库各约 1Gi 内存、2Gi 存储卷）

**Scale/Scope**: 约 20 台设备、约 80 人、13 + 7 + 8 张表；默认 12 个月约 104 万行，最小 1 个月约 8.6 万行

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 检查 | 结论 |
| --- | --- | --- |
| I 测试驱动 | 单元（工厂规则、可复现、按月独立、案例与答案）、集成（Testcontainers 中的 MySQL、PostgreSQL）、集群（Doris 与模拟源系统冒烟）测试先行；覆盖率 ≥ 80% | 通过 |
| II 微服务与契约 | 不新增服务；命令行契约见 [contracts/cli.md](contracts/cli.md)，案例答案格式见 [contracts/case-answer.schema.json](contracts/case-answer.schema.json)；不读写其他服务的库（`mock_dw` 为本特性独占的 database） | 通过 |
| III 开源与许可 | 新增 Faker（MIT）；MySQL 社区版为 GPL-2.0，仅作开发测试设施，不进入交付物（不入 `deploy/components/`、不入离线交付包），见 research R4 | 通过（附说明） |
| IV 最小权限与审计 | 全部为合成数据，不含真实个人或企业信息；`mock_dw` 另设只读账号供后续采集与查询使用；不放入客户环境 | 通过 |
| V 可观测性 | 命令行工具，输出结构化进度与摘要；不涉及服务指标与追踪 | 不适用 |
| VI 以服务方式集成 | MySQL、PostgreSQL 用官方镜像与已有 operator，仅配置；不改上游源码 | 通过 |
| 部署约束 | 只在本地环境；离线模式下跳过模拟源系统 | 通过 |
| 开发流程 | Spec Kit 流程；交付 `acceptance.md` 由产品负责人手动验收 | 通过 |

Phase 1 设计后复核：无新增违例。

### 开源服务清单

| 组件 | 版本 | 许可 | 用途 | 所在位置 | 可替换方案 |
| --- | --- | --- | --- | --- | --- |
| MySQL 社区版 | 8.4 LTS（补丁版本实现时锁定） | GPL-2.0（仅开发测试） | 模拟 MES | `testdata/deploy/mes`（命名空间 `mock-sources`） | MariaDB |
| PostgreSQL | 17.6（与 001 一致） | PostgreSQL | 模拟 QMS | CloudNativePG 实例 `mock-qms` | — |
| CloudNativePG | 1.30.1（已部署） | Apache-2.0 | 管理 `mock-qms` | `cnpg-system` | — |
| Apache Doris | 4.1.5（已部署） | Apache-2.0 | 模拟数仓 `mock_dw` | `contexture` | StarRocks |
| Faker | 实现时锁定 | MIT | 合成姓名、公司名 | `testdata/mockfactory` | Mimesis |
| PyMySQL / asyncpg | 已锁定 | MIT / Apache-2.0 | 写入 MySQL、Doris / PostgreSQL | `testdata/mockfactory` | — |

## Project Structure

### Documentation (this feature)

```text
specs/003-mock-factory-data/
├── spec.md
├── plan.md              # 本文件
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   └── case-answer.schema.json
├── acceptance.md        # 手动验收文档（实现阶段交付）
└── tasks.md             # /speckit-tasks 生成
```

### Source Code (repository root)

```text
testdata/
├── pyproject.toml               # uv workspace 成员 contexture-testdata
├── 数据说明.md                  # 由表定义生成（工厂组成、表与字段、关联键、编号规则、人员名单说明）
├── cases/                       # 标准答案（金标准，人工维护）
│   ├── C1.yaml
│   ├── C2.yaml
│   └── C3.yaml
├── mockfactory/
│   ├── __main__.py              # 命令行：load / checksum / verify-cases / docs / roster
│   ├── config.py                # 基准日、月数、种子、按月派生随机流
│   ├── schema/                  # 表定义（单一来源）：mes.py、qms.py、dw.py → 建表语句与数据说明
│   ├── generate/                # 主数据、生产（工单、批次、报工、投料）、质量（检验、NCR、8D）、设备事件、数仓
│   ├── cases/                   # c1_equipment.py、c2_material.py、c3_fpy.py：在 2026-09 注入案例
│   ├── load/                    # mysql.py、postgres.py、doris.py：批量写入；local 目标的端口转发
│   └── docs.py                  # 数据说明与人员名单
├── deploy/
│   ├── mes/                     # MySQL：Chart（StatefulSet + Service + 初始化账号）与 tests/smoke.sh
│   └── qms/                     # CloudNativePG Cluster mock-qms 与 tests/smoke.sh
└── tests/
    ├── unit/
    ├── integration/             # Testcontainers：MySQL 8.4、PostgreSQL 17
    └── cluster/                 # -m cluster：模拟源系统冒烟、Doris 中的 C3 汇总口径

deploy/helmfile.yaml.gotmpl      # 新增 mock-mes、mock-qms 两个 release（local / lite，离线模式不安装）
tools/up.sh                      # helmfile 同步排除 group=mock-sources（make up 不部署模拟库）
tools/ports.sh                   # 增加 MES 13306、QMS 15432 的转发
Makefile                         # 新增 mock-data 目标（先同步部署 mock-mes、mock-qms，再灌数与核对案例）
pyproject.toml                   # workspace 成员增加 testdata
```

**Structure Decision**：按 ADR-0009 的 `testdata/` 目录组织；生成程序是一个 workspace 包，不是服务。模拟源系统的部署文件跟着
`testdata/` 走而非 `deploy/components/`，以便与交付组件隔离（research R4）。

## 对 spec 的调整

- FR-012 改为“模拟源系统由 `make mock-data` 按需部署到本地环境，不随 `make up` 部署，不进入组件清单与离线交付包”（原文“纳入组件统一管理与离线安装包”），原因见 research R4；
  spec 已同步修改。

## Complexity Tracking

无违例，无需填写。
