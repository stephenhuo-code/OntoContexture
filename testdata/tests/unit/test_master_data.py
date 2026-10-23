"""主数据：工厂组成与编号规则（data-model.md 第 1、2 节）；与种子无关。"""

import re

from conftest_data import dataset

POSITIONS = {
    "操作工",
    "班组长",
    "工艺工程师",
    "质量工程师",
    "检验员",
    "设备维修工",
    "供应商质量工程师",
}


def test_lines_operations_equipment() -> None:
    ds = dataset()
    assert [r["line_code"] for r in ds.records("production_line")] == ["L1", "L2"]
    ops = list(ds.records("operation"))
    for line in ("L1", "L2"):
        assert 6 <= sum(o["line_code"] == line for o in ops) <= 8
    op_by_code = {o["op_code"]: o for o in ops}
    assert all(re.fullmatch(r"L[12]-OP\d0", c) for c in op_by_code)
    equipment = list(ds.records("equipment"))
    assert 18 <= len(equipment) <= 22
    for e in equipment:
        assert re.fullmatch(r"L[12]-[A-Z]{2,3}-\d{2}", e["equip_code"]), e
        op = op_by_code[e["op_code"]]
        assert op["line_code"] == e["line_code"]
        assert op["equip_type"] == e["equip_type"]
    # 每道工序至少有一台设备
    assert {e["op_code"] for e in equipment} == set(op_by_code)
    assert any(e["equip_code"] == "L2-CNC-03" and e["op_code"] == "L2-OP30" for e in equipment)


def test_teams_and_employees() -> None:
    ds = dataset()
    teams = {t["team_code"]: t for t in ds.records("team")}
    for line in ("L1", "L2"):
        assert teams[f"{line}-A"]["shift"] == "白班"
        assert teams[f"{line}-B"]["shift"] == "夜班"
    employees = list(ds.records("employee"))
    assert 75 <= len(employees) <= 85
    assert all(re.fullmatch(r"E\d{4}", e["emp_no"]) for e in employees)
    assert all(e["team_code"] in teams for e in employees)
    assert {e["position"] for e in employees} == POSITIONS
    # 姓名为合成的中文姓名
    assert all(re.fullmatch(r"[一-鿿]{2,4}", e["name"]) for e in employees)


def test_suppliers_customers_materials() -> None:
    ds = dataset()
    assert ds.count("supplier") == 6
    assert ds.count("customer") == 3
    categories = {m["category"] for m in ds.records("material")}
    assert {"成品", "毛坯", "外购件"} <= categories
    codes = {d["code"]: d for d in ds.records("defect_code")}
    assert codes["D101"]["parent_code"] == "D1"
    assert codes["D301"]["name"] == "裂纹"


def test_master_data_independent_of_seed() -> None:
    a, b = dataset(seed=1), dataset(seed=2)
    for table in ("employee", "equipment", "supplier", "customer", "inspection_item"):
        assert a.rows[table] == b.rows[table], table
