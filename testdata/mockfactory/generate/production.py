"""生产数据：物料批次入库、工单、成品批次、工序报工、投料（按月）。

排程是确定的：每条线每天 20 个批次，开工时间固定、当天完工，因此批次号与终检日期与种子无关；
随机的只有设备与操作工的选择、返工与报废数量。2 号线只在终检报废与返工（C3 的投入数因此固定）。
"""

import calendar
import math
import random
from datetime import datetime, timedelta

from mockfactory.generate.draft import Draft
from mockfactory.generate.master import Master

BATCHES_PER_DAY = 20
FIRST_START = timedelta(minutes=20)
INTERVAL = {"L1": timedelta(minutes=42), "L2": timedelta(minutes=52)}
QUEUE = timedelta(minutes=10)
LOT_DAYS = (1, 8, 15, 22)
LOT_QTY = {"M-FG-110": 7000, "M-BR-120": 7000, "M-SL-130": 7000, "M-BAR-210": 13000}


def shift_of(ts: datetime) -> str:
    return "白班" if 8 <= ts.hour < 20 else "夜班"


def team_of(line: str, ts: datetime) -> str:
    return f"{line}-A" if shift_of(ts) == "白班" else f"{line}-B"


def _receive_lots(d: Draft, m: Master) -> None:
    for i, day in enumerate(LOT_DAYS):
        received = datetime(d.year, d.month, day, 0, 5)
        for seq, material in enumerate(LOT_QTY, start=1):
            suppliers = m.lot_suppliers[material]
            supplier = suppliers[i % len(suppliers)]
            d.add(
                "material_lot",
                lot_no=f"ML{d.yymm}{day:02d}-{seq:03d}",
                material_code=material,
                supplier_code=supplier,
                supplier_lot_no=f"SL-{supplier}-{(received - timedelta(days=5)):%y%m%d}",
                received_at=received,
                qty=LOT_QTY[material],
            )


def _yield(line: str, is_final: bool, inp: int, rng: random.Random) -> tuple[int, int]:
    """返回（返工后合格数, 报废数）。"""
    if line == "L1":
        if is_final:
            return rng.choice([0, 0, 0, 1, 1, 2]), 1 if rng.random() < 0.1 else 0
        return 0, 1 if rng.random() < 0.03 else 0
    if is_final:
        return rng.choice([0, 0, 0, 0, 1, 1, 2, 3]), 1 if rng.random() < 0.08 else 0
    return 0, 0


def generate_month(d: Draft, m: Master, rng: random.Random) -> None:
    _receive_lots(d, m)
    lots = sorted(d.rows["material_lot"], key=lambda r: r["received_at"])
    wo_seq = report_seq = cons_seq = 0
    for day in range(1, calendar.monthrange(d.year, d.month)[1] + 1):
        for line in ("L1", "L2"):
            for j in range(BATCHES_PER_DAY):
                start = datetime(d.year, d.month, day) + FIRST_START + j * INTERVAL[line]
                wo_seq += 1
                wo_no = f"WO{d.yymm}-{wo_seq:04d}"
                batch_no = f"B{d.yymm}{day:02d}-{line}-{j + 1:02d}"
                qty = m.batch_qty[line]
                product = m.product_of[line]
                t, inp = start, qty
                finished = start
                for op in m.operations[line]:
                    end = t + timedelta(minutes=math.ceil(inp * op.std_cycle_sec / 60))
                    team = team_of(line, t)
                    rework, scrap = _yield(line, op.is_final, inp, rng)
                    report_seq += 1
                    d.add(
                        "operation_report",
                        report_id=f"R{d.yymm}-{report_seq:06d}",
                        batch_no=batch_no,
                        op_code=op.op_code,
                        equip_code=rng.choice(m.equipment[op.op_code]),
                        operator_no=rng.choice(m.operators(team)),
                        team_code=team,
                        shift=shift_of(t),
                        started_at=t,
                        ended_at=end,
                        input_qty=inp,
                        good_qty=inp - rework - scrap,
                        rework_qty=rework,
                        scrap_qty=scrap,
                    )
                    inp -= scrap
                    finished = end
                    t = end + QUEUE
                d.add(
                    "work_order", wo_no=wo_no, product_code=product, line_code=line,
                    plan_qty=qty, planned_start=start, status="已完工",
                )  # fmt: skip
                d.add(
                    "production_batch", batch_no=batch_no, wo_no=wo_no, product_code=product,
                    line_code=line, qty=qty, started_at=start, finished_at=finished,
                )  # fmt: skip
                for material in m.bom[line]:
                    lot = [
                        x
                        for x in lots
                        if x["material_code"] == material and x["received_at"] <= start
                    ][-1]
                    cons_seq += 1
                    d.add(
                        "material_consumption", consumption_id=f"C{d.yymm}-{cons_seq:05d}",
                        wo_no=wo_no, batch_no=batch_no, lot_no=lot["lot_no"],
                        material_code=material, qty=qty, consumed_at=start,
                    )  # fmt: skip
