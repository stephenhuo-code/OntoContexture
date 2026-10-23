"""3 个案例在内存数据集上的事实（data-model.md 第 7 节）；正常数据中没有同类异常（FR-009）。"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from conftest_data import dataset

from mockfactory.dataset import Dataset

C1_BATCHES = ["B260911-L2-02", "B260911-L2-03", "B260911-L2-04"]
C2_BATCHES = [
    "B260915-L1-01", "B260915-L1-02", "B260916-L1-01", "B260916-L1-02", "B260917-L1-01",
    "B260917-L1-02",
]  # fmt: skip
C2_CRACKED = {"B260915-L1-01", "B260915-L1-02", "B260916-L1-01", "B260917-L1-01"}


def test_c1_equipment_failure() -> None:
    ds = dataset()
    events = [
        (e["event_time"], e["event_type"], e["alarm_code"])
        for e in ds.records("equipment_event")
        if e["equip_code"] == "L2-CNC-03" and e["event_type"] in ("预警", "停机", "维修")
    ]
    assert sorted(events) == [
        (datetime(2026, 9, 8, 10, 15), "预警", "SP-VIB"),
        (datetime(2026, 9, 12, 2, 30), "停机", "SP-STOP"),
        (datetime(2026, 9, 12, 9, 30), "维修", None),
    ]
    night = [
        r for r in ds.records("operation_report")
        if r["op_code"] == "L2-OP30" and r["equip_code"] == "L2-CNC-03"
        and datetime(2026, 9, 10, 20) <= r["started_at"] < datetime(2026, 9, 11, 8)
    ]  # fmt: skip
    assert sorted(r["batch_no"] for r in night) == C1_BATCHES
    assert {(r["operator_no"], r["team_code"], r["shift"]) for r in night} == {
        ("E0047", "L2-B", "夜班")
    }
    # 停机期间与案例窗口内，L2-CNC-03 没有其他精车报工
    others = [
        r for r in ds.records("operation_report")
        if r["equip_code"] == "L2-CNC-03" and r["batch_no"] not in C1_BATCHES
        and datetime(2026, 9, 11) <= r["started_at"] < datetime(2026, 9, 12, 9, 30)
    ]  # fmt: skip
    assert others == []
    records = {r["insp_no"]: r for r in ds.records("inspection_record")}
    bad = [
        (records[v["insp_no"]]["batch_no"], v["measured_value"])
        for v in ds.records("inspection_value")
        if v["item_code"] == "I-L2-OD80" and v["judgement"] == "不合格"
    ]
    assert {b for b, _ in bad} == set(C1_BATCHES)
    assert len(bad) == 10
    assert all(value > Decimal("80.020") for _, value in bad)
    ncr = next(n for n in ds.records("ncr") if n["ncr_no"] == "NCR-2609-0901")
    assert (ncr["source"], ncr["batch_no"], ncr["defect_code"], ncr["responsible_op"]) == (
        "客诉", "B260911-L2-03", "D101", "L2-OP30",
    )  # fmt: skip
    assert any(e["ncr_no"] == "NCR-2609-0901" for e in ds.records("eight_d"))


def test_c2_material_lot() -> None:
    ds = dataset()
    lot = next(x for x in ds.records("material_lot") if x["lot_no"] == "ML260902-901")
    assert (lot["supplier_code"], lot["supplier_lot_no"]) == ("S03", "SL-S03-260828")
    users = sorted(
        c["batch_no"] for c in ds.records("material_consumption") if c["lot_no"] == "ML260902-901"
    )
    assert users == C2_BATCHES
    records = {r["insp_no"]: r for r in ds.records("inspection_record")}
    cracks: dict[str, Decimal] = {}
    for v in ds.records("inspection_value"):
        if v["item_code"] == "I-L1-MT":
            batch = records[v["insp_no"]]["batch_no"]
            cracks[batch] = cracks.get(batch, Decimal(0)) + v["measured_value"]
    assert {b for b, n in cracks.items() if n > 0} == C2_CRACKED
    incoming = [
        v["measured_value"]
        for v in ds.records("inspection_value")
        if records[v["insp_no"]]["lot_no"] == "ML260902-901"
    ]
    assert len(incoming) == 5
    assert all(Decimal(28) <= h < Decimal(29) for h in incoming)
    ncr = next(n for n in ds.records("ncr") if n["ncr_no"] == "NCR-2609-0902")
    assert (ncr["lot_no"], ncr["defect_code"], ncr["found_at"]) == (
        "ML260902-901",
        "D301",
        datetime(2026, 9, 18, 9),
    )


def test_c3_fpy() -> None:
    ds = dataset()
    row = next(
        r for r in ds.records("dws_line_monthly_quality")
        if r["line_code"] == "L2" and r["stat_month"] == "2026-09"
    )  # fmt: skip
    assert (row["input_qty"], row["first_pass_qty"], row["rework_ok_qty"], row["scrap_qty"]) == (
        60000, 59213, 720, 67,
    )  # fmt: skip
    assert row["fpy_incl_rework"] == Decimal("0.9989")
    assert row["fpy_strict"] == Decimal("0.9869")


def test_cases_independent_of_seed() -> None:
    a, b = dataset(seed=1), dataset(seed=2)
    for table in ("ncr", "eight_d", "equipment_event", "material_lot"):
        case_a = [r for r in a.rows[table] if "-090" in str(r[0]) or "-901" in str(r[0])]
        case_b = [r for r in b.rows[table] if "-090" in str(r[0]) or "-901" in str(r[0])]
        assert case_a == case_b and case_a, table

    def month(ds: Dataset) -> dict[str, Any]:
        return next(r for r in ds.records("dws_line_monthly_quality") if r["line_code"] == "L2")

    assert month(a) == month(b)
