"""质量数据与设备事件：只看正常数据（不含案例），检查“不会出现案例类异常”（FR-009）。"""

from collections import defaultdict
from decimal import Decimal

from conftest_data import dataset


def test_inspection_records_reference_real_work() -> None:
    ds = dataset(cases=False)
    reports = {(r["batch_no"], r["op_code"]): r for r in ds.records("operation_report")}
    lots = {lot["lot_no"] for lot in ds.records("material_lot")}
    records = list(ds.records("inspection_record"))
    assert {r["insp_type"] for r in records} == {"来料", "过程", "终检"}
    for rec in records:
        if rec["insp_type"] == "来料":
            assert rec["lot_no"] in lots
            assert rec["batch_no"] is None
        else:
            report = reports[(rec["batch_no"], rec["op_code"])]
            assert rec["equip_code"] == report["equip_code"]
            assert report["started_at"] <= rec["inspected_at"]


def test_normal_values_within_tolerance() -> None:
    ds = dataset(cases=False)
    items = {i["item_code"]: i for i in ds.records("inspection_item")}
    values = list(ds.records("inspection_value"))
    count: dict[str, int] = defaultdict(int)
    for v in values:
        item = items[v["item_code"]]
        assert item["lower_limit"] <= v["measured_value"] <= item["upper_limit"], v
        assert v["judgement"] == "合格"
        count[v["insp_no"]] += 1
    records = {r["insp_no"]: r for r in ds.records("inspection_record")}
    assert set(count) == set(records)
    assert all(r["result"] == "合格" for r in records.values())


def test_incoming_hardness_mid_range() -> None:
    ds = dataset(cases=False)
    hardness = [
        v["measured_value"] for v in ds.records("inspection_value") if v["item_code"] == "I-FG-HRC"
    ]
    assert hardness
    assert all(Decimal("29.5") <= h <= Decimal("32.5") for h in hardness)


def test_equipment_events_have_no_spindle_alarms() -> None:
    ds = dataset(cases=False)
    events = list(ds.records("equipment_event"))
    assert {e["event_type"] for e in events} == {"计划保养", "报警"}
    assert not any((e["alarm_code"] or "").startswith("SP-") for e in events)


def test_ncr_and_8d() -> None:
    ds = dataset(cases=False)
    batches = {b["batch_no"] for b in ds.records("production_batch")}
    defects = {d["code"] for d in ds.records("defect_code")}
    ncrs = list(ds.records("ncr"))
    assert 10 <= len(ncrs) <= 40
    for n in ncrs:
        assert n["batch_no"] in batches
        assert n["defect_code"] in defects
        # 正常数据避开案例的组合
        assert (n["defect_code"], n["responsible_op"]) != ("D101", "L2-OP30")
        assert n["defect_code"] != "D301"
        assert not n["ncr_no"].endswith(("0901", "0902"))
    ncr_nos = {n["ncr_no"] for n in ncrs}
    eight_d = list(ds.records("eight_d"))
    assert eight_d
    assert all(e["ncr_no"] in ncr_nos for e in eight_d)
