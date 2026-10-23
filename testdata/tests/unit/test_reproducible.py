"""可复现（FR-006、SC-002）、按月独立（R5）与引用完整（SC-004）。"""

from conftest_data import dataset

from mockfactory.checksum import dataset_checksums


def test_same_parameters_same_rows() -> None:
    from mockfactory.config import Settings
    from mockfactory.generate import build

    a = build(Settings(months=1, seed=7))
    b = build(Settings(months=1, seed=7))
    assert a.rows == b.rows
    assert dataset_checksums(a) == dataset_checksums(b)


def test_september_identical_at_any_scale() -> None:
    small, larger = dataset(months=1), dataset(months=2)
    for table, rows in small.rows.items():
        assert set(rows) <= set(larger.rows[table]), table
    assert larger.total() > small.total()


def test_different_seed_changes_data() -> None:
    assert dataset(seed=1).rows["inspection_value"] != dataset(seed=2).rows["inspection_value"]


def test_references_valid() -> None:
    ds = dataset()

    def keys(table: str, col: str) -> set[object]:
        return {r[col] for r in ds.records(table)}

    checks = [
        ("production_batch", "wo_no", "work_order", "wo_no"),
        ("operation_report", "batch_no", "production_batch", "batch_no"),
        ("operation_report", "op_code", "operation", "op_code"),
        ("operation_report", "equip_code", "equipment", "equip_code"),
        ("operation_report", "operator_no", "employee", "emp_no"),
        ("operation_report", "team_code", "team", "team_code"),
        ("material_consumption", "lot_no", "material_lot", "lot_no"),
        ("material_consumption", "batch_no", "production_batch", "batch_no"),
        ("material_lot", "supplier_code", "supplier", "supplier_code"),
        ("material_lot", "material_code", "material", "material_code"),
        ("equipment_event", "equip_code", "equipment", "equip_code"),
        ("equipment_event", "handled_by", "employee", "emp_no"),
        ("employee", "team_code", "team", "team_code"),
        ("inspection_value", "insp_no", "inspection_record", "insp_no"),
        ("inspection_value", "item_code", "inspection_item", "item_code"),
        ("inspection_record", "inspector_no", "employee", "emp_no"),
        ("ncr", "defect_code", "defect_code", "code"),
        ("ncr", "reported_by", "employee", "emp_no"),
        ("eight_d", "ncr_no", "ncr", "ncr_no"),
        ("eight_d", "leader_no", "employee", "emp_no"),
    ]
    for table, col, ref_table, ref_col in checks:
        values = {v for v in keys(table, col) if v is not None}
        assert values <= keys(ref_table, ref_col), f"{table}.{col} → {ref_table}.{ref_col}"
    for col, ref in (("batch_no", "production_batch"), ("lot_no", "material_lot")):
        for table in ("inspection_record", "ncr"):
            values = {v for v in keys(table, col) if v is not None}
            assert values <= keys(ref, col), f"{table}.{col}"
