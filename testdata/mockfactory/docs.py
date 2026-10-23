"""数据说明（testdata/数据说明.md）与人员名单（CSV），均由表定义与主数据生成（research R9）。"""

import csv
import io
from pathlib import Path

from mockfactory.generate.master import CUSTOMERS, MATERIALS, SUPPLIERS, TEAMS, build_master
from mockfactory.schema import DIALECT_OF, SYSTEMS, tables_of

DOC_PATH = Path(__file__).resolve().parents[1] / "数据说明.md"

SYSTEM_TITLES = {
    "mes": "模拟 MES（MySQL 8.4，database `mes`）",
    "qms": "模拟 QMS（PostgreSQL 17，database `qms`）",
    "dw": "模拟数仓（Doris，database `mock_dw`）",
}
NUMBERING = [
    ("产线", "`L1`、`L2`", "MES、QMS、数仓"),
    ("工序编码", "`L2-OP30`", "MES、QMS、数仓"),
    ("设备编号", "`L2-CNC-03`", "MES、QMS（过程检验）、数仓"),
    ("工号", "`E0047`", "MES（报工）、QMS（检验员、报告人、8D 组长）、人员名单（飞书）"),
    ("班组", "`L2-B`（2 号线乙班）", "MES、人员名单（飞书）"),
    ("工单号", "`WO2609-0561`（月内序号）", "MES、数仓"),
    ("成品批次号", "`B260911-L2-03`（日期 + 产线 + 当日序号）", "MES、QMS、数仓"),
    (
        "物料批次号",
        "`ML260902-901`；供应商批次 `SL-S03-260828`",
        "MES（入库、投料）、QMS（来料检验、NCR）",
    ),
    ("检验单号", "过程与终检 `IP2609-00001`，来料 `IL2609-0001`", "QMS、数仓"),
    ("NCR 号", "`NCR-2609-0001`；`0901` 起留给案例", "QMS、数仓"),
    ("8D 报告号", "`8D-2609-0001`；`0901` 起留给案例", "QMS"),
    ("设备事件编号", "`EV2609-0001`；`0901` 起留给案例", "MES"),
]
JOINS = [
    (
        "MES `production_batch.batch_no`",
        "QMS `inspection_record.batch_no`、`ncr.batch_no`",
        "批次的检验与不合格",
    ),
    (
        "MES `operation_report.equip_code`",
        "QMS `inspection_record.equip_code`",
        "过程检验对应的加工设备",
    ),
    (
        "MES `material_lot.lot_no`",
        "QMS `inspection_record.lot_no`、`ncr.lot_no`",
        "物料批次的来料检验与不合格",
    ),
    ("MES `employee.emp_no`", "QMS `inspector_no`、`reported_by`、`leader_no`", "人员"),
    ("MES `operation_report.report_id`", "数仓 `dwd_operation_report.report_id`", "报工明细"),
    ("QMS `inspection_value` 主键", "数仓 `dwd_inspection_value` 主键", "检验实测值明细"),
]


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
        *("| " + " | ".join(r) + " |" for r in rows),
    ]


def render_roster() -> str:
    m = build_master()
    teams = {code: (line, shift) for code, _name, line, shift, _n, _p in TEAMS}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["工号", "姓名", "岗位", "班组", "班次", "产线"])
    for team, members in m.teams.items():
        line, shift = teams[team]
        for emp in members:
            writer.writerow([emp, m.names[emp], m.positions[emp], team, shift, line or ""])
    return buf.getvalue()


def render_docs() -> str:
    m = build_master()
    out = [
        "# 模拟工厂数据说明",
        "",
        "由 `uv run python -m mockfactory docs` 依据表定义（`testdata/mockfactory/schema/`）"
        "与主数据生成，请勿手工编辑。",
        "全部为合成数据，不含真实个人或企业信息。"
        "生成与写入见 `make mock-data`（specs/003-mock-factory-data）。",
        "",
        "## 1. 工厂组成",
        "",
        "一家汽车零部件厂：2 条产线、19 台设备、80 人、6 家供应商、3 家客户。"
        "数据覆盖基准日 2026-09-30 之前的 1–12 个月"
        "（默认 12 个月），每条线每天 20 个批次、当天完工。",
        "",
    ]
    rows = []
    for line, ops in m.operations.items():
        for op in ops:
            rows.append([
                line, f"`{op.op_code}`", op.name, op.equip_type,
                "、".join(f"`{e}`" for e in m.equipment[op.op_code]), str(op.std_cycle_sec),
            ])  # fmt: skip
    out += _table(["产线", "工序", "名称", "设备类型", "设备", "单件节拍（秒）"], rows)
    out += ["", "物料、供应商与客户：", ""]
    out += _table(
        ["物料", "名称", "类别", "规格"], [[f"`{c}`", n, k, s] for c, n, k, s, _ in MATERIALS]
    )
    out += [""]
    out += _table(["供应商", "名称", "供货"], [[f"`{c}`", n, s] for c, n, s in SUPPLIERS])
    out += [""]
    out += _table(["客户", "名称"], [[f"`{c}`", n] for c, n in CUSTOMERS])
    out += ["", "## 2. 编号规则", ""]
    out += _table(["编号", "格式示例", "出现在"], [list(r) for r in NUMBERING])
    out += ["", "## 3. 跨系统关联键", ""]
    out += _table(["从", "到", "用途"], [list(r) for r in JOINS])
    out += [
        "",
        "## 4. 案例",
        "",
        "3 个带标准答案的案例都在 2026-09，在任何规模下都相同；答案与逐步查询见 `testdata/cases/`，"
        "`uv run python -m mockfactory verify-cases --target local` 自动核对。",
        "",
    ]
    out += _table(
        ["案例", "场景", "入口"],
        [
            ["C1 设备故障追溯", "P1", "`NCR-2609-0901`（客诉）"],
            ["C2 来料不良追溯", "P1", "`NCR-2609-0902`（内部）"],
            ["C3 一次合格率口径分歧", "P2", "2 号线 2026-09 一次合格率"],
        ],
    )
    out += ["", "## 5. 表与字段", ""]
    for system in SYSTEMS:
        out += [f"### {SYSTEM_TITLES[system]}", ""]
        for t in tables_of(system):
            out += [f"#### `{t.name}` {t.comment}", ""]
            out += _table(
                ["字段", "类型", "主键", "说明"],
                [
                    [f"`{c.name}`", c.type, "是" if c.name in t.primary_key else "", c.comment]
                    for c in t.columns
                ],
            )
            out += [""]
        out += [f"建表方言：{DIALECT_OF[system]}。", ""]
    out += [
        "## 6. 人员与班组",
        "",
        "名单可用 `uv run python -m mockfactory roster --out roster.csv` 导出，"
        "010 搭建飞书测试租户时直接使用。",
        "",
    ]
    reader = csv.reader(io.StringIO(render_roster()))
    header = next(reader)
    out += _table(header, [r for r in reader])
    return "\n".join(out) + "\n"


def write_docs(path: Path = DOC_PATH) -> Path:
    path.write_text(render_docs(), encoding="utf-8")
    return path
