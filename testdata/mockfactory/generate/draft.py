"""单月的生成草稿：行以字典保存，便于案例在写入数据集之前修改；编号在月内编排。"""

from collections import defaultdict
from typing import Any

from mockfactory.dataset import Dataset


class Draft:
    def __init__(self, year: int, month: int) -> None:
        self.year = year
        self.month = month
        self.yymm = f"{year % 100:02d}{month:02d}"
        self.rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(self, table: str, **values: Any) -> dict[str, Any]:
        self.rows[table].append(values)
        return values

    def find(self, table: str, **match: Any) -> list[dict[str, Any]]:
        return [r for r in self.rows[table] if all(r[k] == v for k, v in match.items())]

    def one(self, table: str, **match: Any) -> dict[str, Any]:
        found = self.find(table, **match)
        if len(found) != 1:
            raise LookupError(f"{table} {match}：找到 {len(found)} 行")
        return found[0]

    def flush(self, ds: Dataset) -> None:
        for table, rows in self.rows.items():
            for row in rows:
                ds.add(table, **row)
