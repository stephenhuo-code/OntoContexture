"""人员与班组名单（CSV）：供 010 搭建飞书测试租户。"""

import csv
import io
from pathlib import Path

import pytest
from conftest_data import dataset

from mockfactory.__main__ import main
from mockfactory.docs import render_roster


def test_roster_columns_and_count() -> None:
    rows = list(csv.reader(io.StringIO(render_roster())))
    assert rows[0] == ["工号", "姓名", "岗位", "班组", "班次", "产线"]
    assert len(rows) - 1 == dataset().count("employee")
    by_emp = {r[0]: r for r in rows[1:]}
    assert by_emp["E0047"][3:] == ["L2-B", "夜班", "L2"]
    assert by_emp["E0080"][2] == "供应商质量工程师"


def test_roster_stable_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert render_roster() == render_roster()
    out = tmp_path / "roster.csv"
    assert main(["roster", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == render_roster()
    assert main(["roster"]) == 0
    assert capsys.readouterr().out.startswith("工号,姓名")
