"""verify-cases：执行 testdata/cases/*.yaml 中的只读查询，与标准答案逐项比对。

未提供的目标系统（如 dsn 目标没有数仓）对应的步骤跳过，不算失败。
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from mockfactory.checksum import normalize
from mockfactory.load import Targets
from mockfactory.load import doris as doris_load
from mockfactory.load import mysql as mysql_load
from mockfactory.load import postgres as pg_load

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"


@dataclass
class StepResult:
    case: str
    index: int
    description: str
    status: str  # 通过 / 失败 / 跳过
    detail: str = ""


def _query(t: Targets, system: str, sql: str) -> list[tuple[Any, ...]] | None:
    if system == "mes" and t.mes:
        conn = mysql_load.connect(t.mes, mysql_load.DATABASE)
    elif system == "dw" and t.dw:
        conn = mysql_load.connect(t.dw, doris_load.DATABASE)
    elif system == "qms" and t.qms:
        return pg_load.query(t.qms, sql)
    else:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())
    finally:
        conn.close()


def _cell_equal(actual: Any, expected: Any, tolerance: Decimal) -> bool:
    if expected is None:
        return actual is None
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        try:
            return abs(Decimal(str(actual)) - Decimal(str(expected))) <= tolerance
        except (InvalidOperation, TypeError):
            return False
    return normalize(actual) == str(expected)


def _sorted(rows: list[list[Any]], columns: list[str], order_by: list[str]) -> list[list[Any]]:
    if not order_by:
        return rows
    idx = [columns.index(c) for c in order_by]
    return sorted(rows, key=lambda r: tuple(normalize(r[i]) for i in idx))


def _show(rows: list[list[Any]]) -> str:
    return "\n".join("      " + " | ".join(normalize(v) for v in r) for r in rows) or "      （无）"


def check_step(case: str, index: int, step: dict[str, Any], t: Targets) -> StepResult:
    exp = step["expected"]
    result = _query(t, step["system"], step["sql"])
    if result is None:
        return StepResult(case, index, step["description"], "跳过", f"未提供 {step['system']}")
    order_by = exp.get("order_by", [])
    actual = _sorted([list(r) for r in result], exp["columns"], order_by)
    expected = _sorted([list(r) for r in exp["rows"]], exp["columns"], order_by)
    tolerance = Decimal(str(exp.get("tolerance", 0)))
    same = len(actual) == len(expected) and all(
        len(a) == len(e) and all(_cell_equal(x, y, tolerance) for x, y in zip(a, e, strict=True))
        for a, e in zip(actual, expected, strict=True)
    )
    if same:
        return StepResult(case, index, step["description"], "通过")
    detail = f"    期望：\n{_show(expected)}\n    实际：\n{_show(actual)}"
    return StepResult(case, index, step["description"], "失败", detail)


def verify(t: Targets, cases_dir: Path = CASES_DIR) -> list[StepResult]:
    results: list[StepResult] = []
    for path in sorted(cases_dir.glob("C*.yaml")):
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        for i, step in enumerate(case["steps"], start=1):
            results.append(check_step(case["id"], i, step, t))
    return results


def report(results: list[StepResult]) -> str:
    lines: list[str] = []
    for r in results:
        lines.append(f"{r.case} 步骤 {r.index} {r.status}：{r.description}")
        if r.status != "通过" and r.detail:
            lines.append(r.detail)
    counts = {s: sum(r.status == s for r in results) for s in ("通过", "失败", "跳过")}
    lines.append(
        f"\n合计 {len(results)} 步：通过 {counts['通过']}，"
        f"失败 {counts['失败']}，跳过 {counts['跳过']}"
    )
    return "\n".join(lines) + "\n"
