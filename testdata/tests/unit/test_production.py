"""生产数据：工单、批次、报工、投料的规则（data-model.md 第 3 节）。"""

from collections import defaultdict
from datetime import datetime
from typing import Any

from conftest_data import dataset


def _shift(ts: datetime) -> str:
    return "白班" if 8 <= ts.hour < 20 else "夜班"


def test_work_orders_and_batches() -> None:
    ds = dataset()
    wos = {w["wo_no"]: w for w in ds.records("work_order")}
    batches = list(ds.records("production_batch"))
    assert 900 <= len(batches) <= 1200
    assert len(wos) == len(batches)
    assert {b["wo_no"] for b in batches} == set(wos)
    for b in batches:
        assert wos[b["wo_no"]]["line_code"] == b["line_code"]
        # 当天投产、当天完工
        assert b["started_at"] < b["finished_at"]
        assert b["started_at"].date() == b["finished_at"].date()


def test_reports_follow_routing_and_shifts() -> None:
    ds = dataset()
    ops = {o["op_code"]: o for o in ds.records("operation")}
    routing: dict[str, list[str]] = defaultdict(list)
    for o in sorted(ops.values(), key=lambda o: o["seq"]):
        routing[o["line_code"]].append(o["op_code"])
    equipment = {e["equip_code"]: e for e in ds.records("equipment")}
    employees = {e["emp_no"]: e for e in ds.records("employee")}
    teams = {t["team_code"]: t for t in ds.records("team")}
    batches = {b["batch_no"]: b for b in ds.records("production_batch")}
    by_batch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in ds.records("operation_report"):
        by_batch[r["batch_no"]].append(r)
    assert set(by_batch) == set(batches)
    for batch_no, reports in by_batch.items():
        batch = batches[batch_no]
        reports.sort(key=lambda r: int(ops[str(r["op_code"])]["seq"]))
        assert [r["op_code"] for r in reports] == routing[batch["line_code"]]
        prev = None
        for r in reports:
            assert equipment[r["equip_code"]]["op_code"] == r["op_code"]
            assert employees[r["operator_no"]]["team_code"] == r["team_code"]
            assert teams[r["team_code"]]["line_code"] == batch["line_code"]
            assert r["shift"] == _shift(r["started_at"]) == teams[r["team_code"]]["shift"]
            assert r["started_at"] < r["ended_at"]
            assert r["input_qty"] == r["good_qty"] + r["rework_qty"] + r["scrap_qty"]
            if prev is not None:
                assert r["started_at"] >= prev["ended_at"]
                assert r["input_qty"] == prev["good_qty"] + prev["rework_qty"]
            prev = r
        assert reports[0]["input_qty"] == batch["qty"]


def test_line2_only_scraps_at_final_inspection() -> None:
    """2 号线只在终检报废，终检投入恒为批次数量（C3 的投入数因此与种子无关）。"""
    ds = dataset()
    for r in ds.records("operation_report"):
        if r["op_code"].startswith("L2-") and r["op_code"] != "L2-OP60":
            assert r["scrap_qty"] == 0
            assert r["rework_qty"] == 0
            assert r["input_qty"] == 100


def test_consumption_uses_received_lots() -> None:
    ds = dataset()
    lots = {lot["lot_no"]: lot for lot in ds.records("material_lot")}
    batches = {b["batch_no"]: b for b in ds.records("production_batch")}
    consumptions = list(ds.records("material_consumption"))
    assert consumptions
    for c in consumptions:
        lot = lots[c["lot_no"]]
        assert lot["material_code"] == c["material_code"]
        assert lot["received_at"] <= c["consumed_at"]
        assert batches[c["batch_no"]]["wo_no"] == c["wo_no"]
    # 每个 1 号线批次都投了毛坯
    l1 = {b for b, v in batches.items() if v["line_code"] == "L1"}
    blanks = {c["batch_no"] for c in consumptions if c["material_code"] == "M-FG-110"}
    assert l1 == blanks
