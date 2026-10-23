"""质量数据与设备事件（按月）：来料、过程、终检检验，NCR 与 8D，设备的计划保养与一般报警。

正常数据的约束（data-model.md 第 7 节）：实测值在公差带中部、来料硬度在合格区间中段、
设备事件不含主轴类预警、
NCR 不使用案例的“缺陷码 + 责任工序”组合（D101 + L2-OP30）与缺陷码 D301。
NCR、8D 与设备事件的 0901 起编号留给案例。
"""

import calendar
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from mockfactory.generate.draft import Draft
from mockfactory.generate.master import Item, Master
from mockfactory.generate.production import shift_of

SAMPLES = 5
ALARMS = [
    ("AL-COOL", "冷却液液位低"),
    ("AL-DOOR", "安全门未关闭"),
    ("AL-TOOL", "刀具寿命到期"),
    ("AL-AIR", "气源压力不足"),
]
# 缺陷码 → 可能的责任工序
DEFECT_OPS = {
    "D101": ["L1-OP30", "L1-OP60"],
    "D102": ["L2-OP40"],
    "D103": ["L1-OP10", "L2-OP10"],
    "D201": ["L1-OP80", "L2-OP60"],
    "D202": ["L1-OP70", "L2-OP50"],
    "D203": ["L2-OP50"],
    "D302": ["L1-OP50"],
    "D401": ["L1-OP70"],
    "D402": ["L1-OP70"],
}
DEFECT_NAMES = {
    "D101": "外径超差", "D102": "孔径超差", "D103": "长度超差", "D201": "划伤", "D202": "磕碰伤",
    "D203": "锈蚀", "D302": "硬度不足", "D401": "漏装", "D402": "轴承异响",
}  # fmt: skip
ROOT_CAUSES = {
    "D1": ("机", "刀具磨损补偿不及时，尺寸逐步偏移"),
    "D2": ("人", "工件转运防护不到位"),
    "D3": ("料", "热处理工艺参数波动"),
    "D4": ("人", "装配作业未按 SOP 自检"),
}


def quantum(item: Item) -> Decimal:
    if item.unit == "mm":
        return Decimal("0.001")
    if item.unit == "处":
        return Decimal("1")
    return Decimal("0.1")


def normal_value(item: Item, rng: random.Random) -> Decimal:
    """公差带中部（中间一半）内的正态值；探伤类恒为 0。"""
    if item.lower == item.upper:
        return item.lower
    width = item.upper - item.lower
    low, high = item.lower + width / 4, item.upper - width / 4
    v = Decimal(str(rng.gauss(float(item.target), float(width) / 12)))
    return min(max(v, low), high).quantize(quantum(item))


def inspector(m: Master, ts: datetime, rng: random.Random) -> str:
    team = "QC-A" if shift_of(ts) == "白班" else "QC-B"
    return rng.choice(m.teams[team])


def add_inspection(
    d: Draft, m: Master, rng: random.Random, items: list[Item], **record: Any
) -> dict[str, Any]:
    insp_no = record.pop("insp_no")
    rec = d.add(
        "inspection_record", insp_no=insp_no, sample_qty=SAMPLES, result="合格",
        inspector_no=inspector(m, record["inspected_at"], rng), **record,
    )  # fmt: skip
    for item in items:
        for s in range(1, SAMPLES + 1):
            d.add(
                "inspection_value", insp_no=insp_no, item_code=item.item_code, sample_seq=s,
                measured_value=normal_value(item, rng), judgement="合格",
            )  # fmt: skip
    return rec


def _inspections(d: Draft, m: Master, rng: random.Random) -> None:
    seq = 0
    for lot in d.rows["material_lot"]:
        items = m.items.get(lot["material_code"])
        if not items:
            continue
        seq += 1
        add_inspection(
            d, m, rng, items, insp_no=f"IL{d.yymm}-{seq:04d}", insp_type="来料",
            batch_no=None, lot_no=lot["lot_no"], op_code=None, equip_code=None,
            inspected_at=lot["received_at"] + timedelta(hours=2),
        )  # fmt: skip
    seq = 0
    for r in d.rows["operation_report"]:
        items = m.items.get(r["op_code"])
        if not items:
            continue
        seq += 1
        add_inspection(
            d, m, rng, items, insp_no=f"IP{d.yymm}-{seq:05d}",
            insp_type=items[0].insp_type, batch_no=r["batch_no"], lot_no=None,
            op_code=r["op_code"], equip_code=r["equip_code"],
            inspected_at=r["ended_at"] - timedelta(minutes=5),
        )  # fmt: skip


def _events(d: Draft, m: Master, rng: random.Random) -> None:
    days = calendar.monthrange(d.year, d.month)[1]
    events: list[dict[str, Any]] = []
    codes = [c for op in sorted(m.equipment) for c in m.equipment[op]]
    for i, code in enumerate(codes):
        events.append({
            "equip_code": code, "event_time": datetime(d.year, d.month, i % 27 + 1, 9, 0),
            "event_type": "计划保养", "alarm_code": None, "description": "月度计划保养",
            "handled_by": rng.choice(m.teams["MT"]),
        })  # fmt: skip
        for _ in range(rng.randint(3, 7)):
            alarm, text = rng.choice(ALARMS)
            ts = datetime(d.year, d.month, 1) + timedelta(minutes=rng.randrange(days * 24 * 60))
            events.append({
                "equip_code": code, "event_time": ts, "event_type": "报警", "alarm_code": alarm,
                "description": text, "handled_by": rng.choice(m.teams["MT"]),
            })  # fmt: skip
    events.sort(key=lambda e: (e["event_time"], e["equip_code"]))
    for seq, e in enumerate(events, start=1):
        d.add("equipment_event", event_id=f"EV{d.yymm}-{seq:04d}", **e)


def _ncrs(d: Draft, m: Master, rng: random.Random) -> None:
    days = calendar.monthrange(d.year, d.month)[1]
    month_end = datetime(d.year, d.month, days, 22, 0)
    batches = d.rows["production_batch"]
    engineers = m.by_position("质量工程师")
    inspectors = m.teams["QC-A"] + m.teams["QC-B"]
    drafts: list[dict[str, Any]] = []
    for _ in range(rng.randint(18, 30)):
        batch = rng.choice(batches)
        line = batch["line_code"]
        defect = rng.choice(
            [c for c, ops in DEFECT_OPS.items() if any(o.startswith(line) for o in ops)]
        )
        op = rng.choice([o for o in DEFECT_OPS[defect] if o.startswith(line)])
        complaint = rng.random() < 0.2
        delay = (
            timedelta(days=rng.randint(3, 15)) if complaint else timedelta(hours=rng.randint(1, 24))
        )
        found = min(batch["finished_at"] + delay, month_end)
        drafts.append({
            "source": "客诉" if complaint else "内部", "batch_no": batch["batch_no"],
            "lot_no": None,
            "product_code": batch["product_code"], "defect_code": defect, "qty": rng.randint(1, 5),
            "found_at": found,
            "reported_by": rng.choice(engineers if complaint else inspectors),
            "responsible_op": op,
            "customer_code": rng.choice(["C01", "C02", "C03"]) if complaint else None,
            "status": "处理中" if found > month_end - timedelta(days=5) else "已关闭",
            "description": f"{DEFECT_NAMES[defect]}，批次 {batch['batch_no']}",
        })  # fmt: skip
    drafts.sort(key=lambda n: (n["found_at"], n["batch_no"]))
    eight_d_seq = 0
    for seq, n in enumerate(drafts, start=1):
        ncr_no = f"NCR-{d.yymm}-{seq:04d}"
        d.add("ncr", ncr_no=ncr_no, **n)
        if n["source"] != "客诉" and rng.random() >= 0.1:
            continue
        eight_d_seq += 1
        category, cause = ROOT_CAUSES[n["defect_code"][:2]]
        opened = n["found_at"] + timedelta(hours=2)
        closed = opened + timedelta(days=rng.randint(5, 20))
        done = closed <= month_end
        d.add(
            "eight_d", report_no=f"8D-{d.yymm}-{eight_d_seq:04d}", ncr_no=ncr_no,
            leader_no=rng.choice(engineers), root_cause_category=category, root_cause=cause,
            containment=f"隔离批次 {n['batch_no']} 的在制与库存并全检",
            corrective_action="更新作业指导书并培训，增加巡检频次",
            opened_at=opened, closed_at=closed if done else None,
            status="已关闭" if done else "进行中",
        )  # fmt: skip


def generate_month(d: Draft, m: Master, rng: random.Random) -> None:
    _inspections(d, m, rng)
    _events(d, m, rng)
    _ncrs(d, m, rng)
