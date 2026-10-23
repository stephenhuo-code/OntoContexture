"""模拟数仓：维度（一次）、明细层 DWD 与汇总层 DWS（按月，由明细重算）。"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from mockfactory.dataset import Dataset
from mockfactory.generate.draft import Draft
from mockfactory.generate.master import MATERIALS, Master

RATE = Decimal("0.0001")


def rate(num: int, den: int) -> Decimal:
    return (Decimal(num) / Decimal(den)).quantize(RATE, rounding=ROUND_HALF_UP)


def add_dims(ds: Dataset, m: Master) -> None:
    for line in m.lines.values():
        ds.add(
            "dim_line", line_code=line["line_code"], line_name=line["name"],
            product_family=line["product_family"],
        )  # fmt: skip
    for r in ds.records("equipment"):
        ds.add(
            "dim_equipment", equip_code=r["equip_code"], equip_name=r["name"],
            equip_type=r["equip_type"], line_code=r["line_code"], op_code=r["op_code"],
        )  # fmt: skip
    names = {code: name for code, name, *_ in MATERIALS}
    for line, product in m.product_of.items():
        ds.add("dim_product", product_code=product, product_name=names[product], line_code=line)


def generate_month(d: Draft, m: Master) -> None:
    batches = {b["batch_no"]: b for b in d.rows["production_batch"]}
    final_ops = {ops[-1].op_code for ops in m.operations.values()}
    daily: dict[tuple[str, object], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for r in d.rows["operation_report"]:
        b = batches[r["batch_no"]]
        is_final = r["op_code"] in final_ops
        d.add(
            "dwd_operation_report", report_id=r["report_id"], report_date=r["started_at"].date(),
            line_code=b["line_code"], product_code=b["product_code"], batch_no=r["batch_no"],
            wo_no=b["wo_no"], op_code=r["op_code"], is_final_op=int(is_final),
            equip_code=r["equip_code"], operator_no=r["operator_no"], team_code=r["team_code"],
            shift=r["shift"], input_qty=r["input_qty"], good_qty=r["good_qty"],
            rework_qty=r["rework_qty"], scrap_qty=r["scrap_qty"],
        )  # fmt: skip
        if is_final:
            s = daily[(b["line_code"], r["started_at"].date())]
            s[0] += r["input_qty"]
            s[1] += r["good_qty"]
            s[2] += r["rework_qty"]
            s[3] += r["scrap_qty"]
    records = {rec["insp_no"]: rec for rec in d.rows["inspection_record"]}
    for v in d.rows["inspection_value"]:
        rec = records[v["insp_no"]]
        batch = batches.get(rec["batch_no"]) if rec["batch_no"] else None
        d.add(
            "dwd_inspection_value", insp_no=v["insp_no"], item_code=v["item_code"],
            sample_seq=v["sample_seq"], insp_date=rec["inspected_at"].date(),
            insp_type=rec["insp_type"], line_code=batch["line_code"] if batch else None,
            batch_no=rec["batch_no"], lot_no=rec["lot_no"], op_code=rec["op_code"],
            equip_code=rec["equip_code"], measured_value=v["measured_value"],
            judgement=v["judgement"],
        )  # fmt: skip
    for n in d.rows["ncr"]:
        batch = batches.get(n["batch_no"]) if n["batch_no"] else None
        d.add(
            "dwd_ncr", ncr_no=n["ncr_no"], found_date=n["found_at"].date(), source=n["source"],
            line_code=batch["line_code"] if batch else None, batch_no=n["batch_no"],
            lot_no=n["lot_no"], product_code=n["product_code"], defect_code=n["defect_code"],
            responsible_op=n["responsible_op"], customer_code=n["customer_code"], qty=n["qty"],
        )  # fmt: skip
    monthly: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for (line, day), s in sorted(daily.items()):
        _add_quality(d, "dws_line_daily_quality", line_code=line, stat_date=day, sums=s)
        acc = monthly[(line, f"{d.year:04d}-{d.month:02d}")]
        for i in range(4):
            acc[i] += s[i]
    for (line, month), s in sorted(monthly.items()):
        _add_quality(d, "dws_line_monthly_quality", line_code=line, stat_month=month, sums=s)


def _add_quality(d: Draft, table: str, sums: list[int], **key: object) -> None:
    inp, good, rework, scrap = sums
    d.add(
        table, **key, input_qty=inp, first_pass_qty=good, rework_ok_qty=rework, scrap_qty=scrap,
        fpy_incl_rework=rate(good + rework, inp), fpy_strict=rate(good, inp),
    )  # fmt: skip
