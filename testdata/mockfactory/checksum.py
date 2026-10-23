"""逐表摘要：按主键排序后对规范化的行计算 SHA-256，数据集与数据库得到相同结果（SC-002）。"""

import hashlib
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from mockfactory.dataset import Dataset
from mockfactory.schema import TABLES

Checksums = dict[tuple[str, str], tuple[int, str]]  # (系统, 表) → (行数, 摘要)


def normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal | float):
        return f"{Decimal(str(value)):.4f}"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def digest(rows: Iterable[tuple[Any, ...]]) -> tuple[int, str]:
    h = hashlib.sha256()
    n = 0
    for row in rows:
        n += 1
        h.update("\x1f".join(normalize(v) for v in row).encode())
        h.update(b"\n")
    return n, h.hexdigest()


def dataset_checksums(ds: Dataset) -> Checksums:
    return {(t.system, t.name): digest(ds.sorted_rows(t.name)) for t in TABLES}


def format_checksums(sums: Checksums) -> str:
    return "".join(f"{s}\t{t}\t{n}\t{h}\n" for (s, t), (n, h) in sorted(sums.items()))
