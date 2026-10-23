"""主数据：工厂组成、人员、物料、供应商、客户、缺陷码、检验项（data-model.md 第 1、2 节）。

主数据固定，不随 --seed 变化：后续特性（010 飞书人员、011 采集）依赖它。
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker

from mockfactory.config import MASTER_SEED
from mockfactory.dataset import Dataset

D = Decimal


@dataclass(frozen=True)
class Operation:
    op_code: str
    line_code: str
    seq: int
    name: str
    equip_type: str
    std_cycle_sec: int
    is_final: bool


@dataclass(frozen=True)
class Item:
    item_code: str
    name: str
    insp_type: str
    op_code: str | None
    material_code: str
    target: Decimal
    lower: Decimal
    upper: Decimal
    unit: str


@dataclass
class Master:
    lines: dict[str, dict[str, object]] = field(default_factory=dict)
    operations: dict[str, list[Operation]] = field(default_factory=dict)  # 产线 → 工艺路线
    equipment: dict[str, list[str]] = field(default_factory=dict)  # 工序 → 设备编号
    teams: dict[str, list[str]] = field(default_factory=dict)  # 班组 → 工号（第一个为班组长）
    positions: dict[str, str] = field(default_factory=dict)  # 工号 → 岗位
    items: dict[str, list[Item]] = field(default_factory=dict)  # 工序或物料 → 检验项
    product_of: dict[str, str] = field(default_factory=dict)  # 产线 → 产品
    batch_qty: dict[str, int] = field(default_factory=dict)
    bom: dict[str, list[str]] = field(default_factory=dict)  # 产线 → 每批投料的物料
    lot_suppliers: dict[str, list[str]] = field(default_factory=dict)  # 物料 → 轮换的供应商
    names: dict[str, str] = field(default_factory=dict)  # 工号 → 姓名（合成）
    hired: dict[str, date] = field(default_factory=dict)
    installed: dict[str, date] = field(default_factory=dict)

    def operators(self, team: str) -> list[str]:
        return self.teams[team][1:]

    def by_position(self, position: str) -> list[str]:
        return [e for e, p in self.positions.items() if p == position]


LINES = [
    ("L1", "1 号线", "输出轴总成"),
    ("L2", "2 号线", "法兰盘"),
]
# (工序, 名称, 设备类型, 单件节拍秒, 设备数)
ROUTING = {
    "L1": [
        ("OP10", "下料", "锯床", 30, 1),
        ("OP20", "粗车", "数控车床", 90, 2),
        ("OP30", "精车", "数控车床", 60, 2),
        ("OP40", "铣键槽", "加工中心", 60, 1),
        ("OP50", "热处理", "热处理炉", 216, 1),
        ("OP60", "磨削", "外圆磨床", 80, 2),
        ("OP70", "装配", "装配压机", 60, 1),
        ("OP80", "终检", "检测台", 40, 1),
    ],
    "L2": [
        ("OP10", "下料", "锯床", 20, 1),
        ("OP20", "粗车", "数控车床", 60, 1),
        ("OP30", "精车", "数控车床", 45, 2),
        ("OP40", "钻孔", "加工中心", 30, 2),
        ("OP50", "清洗", "清洗机", 15, 1),
        ("OP60", "终检", "检测台", 20, 1),
    ],
}
EQUIP_PREFIX = {
    "锯床": ("SAW", "GZ4230"),
    "数控车床": ("CNC", "CK6150"),
    "加工中心": ("MC", "VMC850"),
    "热处理炉": ("HT", "RJ-90-9"),
    "外圆磨床": ("GR", "M1432B"),
    "装配压机": ("PR", "YP-10T"),
    "检测台": ("QC", "JC-200"),
    "清洗机": ("WS", "QX-800"),
}
MATERIALS = [
    ("P-OS-100", "输出轴总成", "成品", "Ø30×220", "件"),
    ("P-FL-200", "法兰盘", "成品", "Ø80×25", "件"),
    ("M-FG-110", "输出轴锻件毛坯", "毛坯", "40Cr", "件"),
    ("M-BR-120", "深沟球轴承", "外购件", "6205", "件"),
    ("M-SL-130", "骨架油封", "外购件", "TC 25×47×7", "件"),
    ("M-BAR-210", "法兰棒料", "原材料", "45# 钢 Ø85", "件"),
]
SUPPLIERS = [
    ("S01", "东岳精密轴承有限公司", "深沟球轴承"),
    ("S02", "青禾密封件有限公司", "骨架油封"),
    ("S03", "鼎锐锻造有限公司", "输出轴锻件毛坯"),
    ("S04", "恒通锻压有限公司", "输出轴锻件毛坯"),
    ("S05", "广川特钢有限公司", "法兰棒料"),
    ("S06", "北原钢材贸易有限公司", "法兰棒料"),
]
CUSTOMERS = [
    ("C01", "远航汽车制造有限公司"),
    ("C02", "星川汽车股份有限公司"),
    ("C03", "澜海新能源汽车有限公司"),
]
DEFECTS = [
    ("D1", "尺寸", None),
    ("D101", "外径超差", "D1"),
    ("D102", "孔径超差", "D1"),
    ("D103", "长度超差", "D1"),
    ("D2", "外观", None),
    ("D201", "划伤", "D2"),
    ("D202", "磕碰伤", "D2"),
    ("D203", "锈蚀", "D2"),
    ("D3", "材料", None),
    ("D301", "裂纹", "D3"),
    ("D302", "硬度不足", "D3"),
    ("D4", "装配", None),
    ("D401", "漏装", "D4"),
    ("D402", "轴承异响", "D4"),
]
# (检验项, 名称, 类型, 工序, 物料, 目标, 下限, 上限, 单位)
ITEMS = [
    ("I-FG-HRC", "毛坯硬度", "来料", None, "M-FG-110", "31", "28", "34", "HRC"),
    ("I-BR-ID", "轴承内径", "来料", None, "M-BR-120", "25", "24.992", "25.008", "mm"),
    ("I-BAR-HB", "棒料硬度", "来料", None, "M-BAR-210", "195", "170", "220", "HB"),
    ("I-L1-OD30", "精车外径", "过程", "L1-OP30", "P-OS-100", "30", "29.98", "30.02", "mm"),
    ("I-L1-LEN", "总长", "过程", "L1-OP30", "P-OS-100", "220", "219.9", "220.1", "mm"),
    ("I-L1-OD25", "轴颈外径", "过程", "L1-OP60", "P-OS-100", "25", "24.99", "25.01", "mm"),
    ("I-L1-OD25F", "轴颈外径（终检）", "终检", "L1-OP80", "P-OS-100", "25", "24.99", "25.01", "mm"),
    ("I-L1-MT", "磁粉探伤", "终检", "L1-OP80", "P-OS-100", "0", "0", "0", "处"),
    ("I-L2-OD80", "精车外径", "过程", "L2-OP30", "P-FL-200", "80", "79.98", "80.02", "mm"),
    ("I-L2-TH", "厚度", "过程", "L2-OP30", "P-FL-200", "25", "24.95", "25.05", "mm"),
    ("I-L2-HOLE", "螺栓孔径", "过程", "L2-OP40", "P-FL-200", "10", "9.985", "10.015", "mm"),
    ("I-L2-OD80F", "外径（终检）", "终检", "L2-OP60", "P-FL-200", "80", "79.97", "80.03", "mm"),
    ("I-L2-FLAT", "平面度", "终检", "L2-OP60", "P-FL-200", "0.01", "0", "0.03", "mm"),
]
# 班组：(编码, 名称, 产线, 班次, 人数, 岗位；第一人为班组长或组长)
TEAMS = [
    ("L1-A", "1 号线甲班", "L1", "白班", 15, "操作工"),
    ("L1-B", "1 号线乙班", "L1", "夜班", 15, "操作工"),
    ("L2-A", "2 号线甲班", "L2", "白班", 15, "操作工"),
    ("L2-B", "2 号线乙班", "L2", "夜班", 15, "操作工"),
    ("QC-A", "质检甲班", None, "白班", 5, "检验员"),
    ("QC-B", "质检乙班", None, "夜班", 4, "检验员"),
    ("MT", "设备维修组", None, "常日班", 5, "设备维修工"),
    ("ENG", "工艺质量组", None, "常日班", 6, None),
]
ENG_POSITIONS = [
    "工艺工程师",
    "工艺工程师",
    "质量工程师",
    "质量工程师",
    "质量工程师",
    "供应商质量工程师",
]


def build_master() -> Master:
    rng = random.Random(f"master-{MASTER_SEED}")  # noqa: S311 仅生成模拟数据
    fake = Faker("zh_CN")
    fake.seed_instance(MASTER_SEED)
    m = Master()
    for code, name, family in LINES:
        m.lines[code] = {"line_code": code, "name": name, "product_family": family}
    m.product_of = {"L1": "P-OS-100", "L2": "P-FL-200"}
    m.batch_qty = {"L1": 50, "L2": 100}
    m.bom = {"L1": ["M-FG-110", "M-BR-120", "M-SL-130"], "L2": ["M-BAR-210"]}
    m.lot_suppliers = {
        "M-FG-110": ["S03", "S04"],
        "M-BR-120": ["S01"],
        "M-SL-130": ["S02"],
        "M-BAR-210": ["S05", "S06"],
    }
    for line, steps in ROUTING.items():
        ops: list[Operation] = []
        counters: dict[str, int] = {}
        for i, (op, name, etype, cycle, n_equip) in enumerate(steps):
            op_code = f"{line}-{op}"
            ops.append(
                Operation(op_code, line, (i + 1) * 10, name, etype, cycle, i == len(steps) - 1)
            )
            prefix = EQUIP_PREFIX[etype][0]
            codes = []
            for _ in range(n_equip):
                counters[prefix] = counters.get(prefix, 0) + 1
                codes.append(f"{line}-{prefix}-{counters[prefix]:02d}")
            m.equipment[op_code] = codes
        m.operations[line] = ops
    emp = 0
    for code, _name, _line, _shift, size, position in TEAMS:
        members = []
        for i in range(size):
            emp += 1
            emp_no = f"E{emp:04d}"
            members.append(emp_no)
            if position is None:
                m.positions[emp_no] = ENG_POSITIONS[i]
            elif position == "操作工" and i == 0:
                m.positions[emp_no] = "班组长"
            else:
                m.positions[emp_no] = position
        m.teams[code] = members
    for row in ITEMS:
        item = Item(row[0], row[1], row[2], row[3], row[4], D(row[5]), D(row[6]), D(row[7]), row[8])
        m.items.setdefault(item.op_code or item.material_code, []).append(item)
    m.names = {e: fake.name() for e in m.positions}
    m.hired = {e: date(2015, 1, 1) + timedelta(days=rng.randrange(0, 3650)) for e in m.positions}
    m.installed = {
        e: date(2016, 1, 1) + timedelta(days=rng.randrange(0, 2900))
        for codes in m.equipment.values()
        for e in codes
    }
    return m


def add_master(ds: Dataset, m: Master) -> None:
    for line in m.lines.values():
        ds.add("production_line", **line)
    for ops in m.operations.values():
        for op in ops:
            ds.add(
                "operation", op_code=op.op_code, line_code=op.line_code, seq=op.seq, name=op.name,
                equip_type=op.equip_type, std_cycle_sec=op.std_cycle_sec,
            )  # fmt: skip
            for code in m.equipment[op.op_code]:
                prefix_model = EQUIP_PREFIX[op.equip_type]
                ds.add(
                    "equipment", equip_code=code, name=f"{op.equip_type}{code[-2:]}#",
                    equip_type=op.equip_type, model=prefix_model[1], line_code=op.line_code,
                    op_code=op.op_code, installed_on=m.installed[code],
                )  # fmt: skip
    for code, name, category, spec, unit in MATERIALS:
        ds.add("material", material_code=code, name=name, category=category, spec=spec, unit=unit)
    for code, name, supplies in SUPPLIERS:
        ds.add("supplier", supplier_code=code, name=name, supplies=supplies)
    for code, name, line, shift, _size, _pos in TEAMS:
        ds.add("team", team_code=code, name=name, line_code=line, shift=shift)
    for team, members in m.teams.items():
        for emp_no in members:
            ds.add(
                "employee", emp_no=emp_no, name=m.names[emp_no],
                position=m.positions[emp_no], team_code=team,
                hired_on=m.hired[emp_no],
            )  # fmt: skip
    for code, name in CUSTOMERS:
        ds.add("customer", customer_code=code, name=name)
    for code, name, parent in DEFECTS:
        category = name if parent is None else next(n for c, n, _ in DEFECTS if c == parent)
        ds.add("defect_code", code=code, name=name, category=category, parent_code=parent)
    for items in m.items.values():
        for i in items:
            ds.add(
                "inspection_item", item_code=i.item_code, name=i.name, insp_type=i.insp_type,
                op_code=i.op_code, material_code=i.material_code, target=i.target,
                lower_limit=i.lower, upper_limit=i.upper, unit=i.unit,
            )  # fmt: skip
