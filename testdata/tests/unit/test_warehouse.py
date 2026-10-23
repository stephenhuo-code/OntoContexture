"""数仓：DWD 与 MES、QMS 明细一一对应；DWS 可由 DWD 重算；两种口径的一次合格率。"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from conftest_data import dataset


def _rate(num: int, den: int) -> Decimal:
    return (Decimal(num) / Decimal(den)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def test_dwd_matches_sources() -> None:
    ds = dataset()
    assert {r["report_id"] for r in ds.records("dwd_operation_report")} == {
        r["report_id"] for r in ds.records("operation_report")
    }
    assert ds.count("dwd_inspection_value") == ds.count("inspection_value")
    assert {r["ncr_no"] for r in ds.records("dwd_ncr")} == {r["ncr_no"] for r in ds.records("ncr")}
    assert ds.count("dim_equipment") == ds.count("equipment")


def test_dws_recomputed_from_dwd() -> None:
    ds = dataset()
    daily: dict[tuple[str, object], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    monthly: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for r in ds.records("dwd_operation_report"):
        if not r["is_final_op"]:
            continue
        for key, acc in (
            ((r["line_code"], r["report_date"]), daily),
            ((r["line_code"], r["report_date"].strftime("%Y-%m")), monthly),
        ):
            s = acc[key]
            s[0] += r["input_qty"]
            s[1] += r["good_qty"]
            s[2] += r["rework_qty"]
            s[3] += r["scrap_qty"]
    for table, acc, period in (
        ("dws_line_daily_quality", daily, "stat_date"),
        ("dws_line_monthly_quality", monthly, "stat_month"),
    ):
        rows = list(ds.records(table))
        assert len(rows) == len(acc)
        for row in rows:
            inp, good, rework, scrap = acc[(row["line_code"], row[period])]
            cols = ("input_qty", "first_pass_qty", "rework_ok_qty", "scrap_qty")
            totals = tuple(row[c] for c in cols)
            assert totals == (inp, good, rework, scrap)
            assert row["fpy_incl_rework"] == _rate(good + rework, inp)
            assert row["fpy_strict"] == _rate(good, inp)
