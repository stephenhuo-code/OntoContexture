"""生成结果：按“表 → 行”保存，行以字典追加、按表的列顺序存为元组。"""

from collections.abc import Iterator
from typing import Any

from mockfactory.schema import TABLES, Table

Row = tuple[Any, ...]


class Dataset:
    def __init__(self) -> None:
        self.tables: dict[str, Table] = {t.name: t for t in TABLES}
        self.rows: dict[str, list[Row]] = {t.name: [] for t in TABLES}

    def add(self, table: str, **values: Any) -> None:
        cols = self.tables[table].column_names
        if set(values) != set(cols):
            missing, extra = set(cols) - set(values), set(values) - set(cols)
            raise KeyError(f"{table}: 缺少 {sorted(missing)}，多出 {sorted(extra)}")
        self.rows[table].append(tuple(values[c] for c in cols))

    def records(self, table: str) -> Iterator[dict[str, Any]]:
        cols = self.tables[table].column_names
        for row in self.rows[table]:
            yield dict(zip(cols, row, strict=True))

    def sorted_rows(self, table: str) -> list[Row]:
        t = self.tables[table]
        idx = [t.column_names.index(k) for k in t.primary_key]
        return sorted(self.rows[table], key=lambda r: tuple(r[i] for i in idx))

    def count(self, table: str) -> int:
        return len(self.rows[table])

    def total(self, system: str | None = None) -> int:
        return sum(
            len(rows)
            for name, rows in self.rows.items()
            if system is None or self.tables[name].system == system
        )
