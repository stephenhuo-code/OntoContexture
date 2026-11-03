"""覆盖率门禁必须拒绝缺报告或不足 80% 的变更。"""

import json
from pathlib import Path

import pytest

from tools.coverage_gate import changed_lines, check_diff, read_lcov, read_python


def test_lcov_relative_paths_and_uncovered_lines(tmp_path: Path) -> None:
    report = tmp_path / "lcov.info"
    report.write_text("SF:src/a.ts\nDA:1,1\nDA:3,0\nend_of_record\n")
    assert read_lcov(report, Path("apps/web")) == {"apps/web/src/a.ts": {1: True, 3: False}}


def test_lcov_shared_extension_paths_are_normalized(tmp_path: Path) -> None:
    report = tmp_path / "lcov.info"
    report.write_text("SF:../../extensions/keycloak/theme.js\nDA:1,1\nend_of_record\n")
    assert read_lcov(report, Path("packages/ui")) == {"extensions/keycloak/theme.js": {1: True}}


def test_python_coverage_formats(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps({"files": {"tools/a.py": {"executed_lines": [1], "missing_lines": [2]}}})
    )
    assert read_python(report) == {"tools/a.py": {1: True, 2: False}}


def test_diff_hunks_include_only_added_lines() -> None:
    diff = (
        "+++ b/apps/web/src/a.ts\n@@ -2,2 +2,3 @@\n-a\n+b\n+c\n+d\n"
        "+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
    )
    assert changed_lines(diff) == {"apps/web/src/a.ts": {2, 3, 4}}


def test_insufficient_coverage_fails_but_80_percent_passes() -> None:
    changes = {"tools/a.py": set(range(1, 6))}
    assert check_diff(changes, {"tools/a.py": {1: True, 2: True, 3: True, 4: True, 5: False}}) == (
        4,
        5,
    )
    with pytest.raises(ValueError, match=r"60\.00%"):
        check_diff(changes, {"tools/a.py": {1: True, 2: True, 3: True, 4: False, 5: False}})


def test_missing_source_report_fails_closed() -> None:
    with pytest.raises(ValueError, match="缺少"):
        check_diff({"apps/web/src/new.ts": {1}}, {})


def test_non_executable_lines_do_not_inflate_coverage() -> None:
    assert check_diff({"tools/a.py": {1, 2, 3}}, {"tools/a.py": {2: True}}) == (1, 1)
