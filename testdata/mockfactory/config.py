"""生成参数：固定基准日、规模（月数）与种子；每个月使用独立的随机流（research R5）。

月数只增减更早的月份；同一（种子, 年月）的随机流相同，因此 2026-09 的数据在任何规模下都相同。
"""

import random
from dataclasses import dataclass
from datetime import date

BASE_DATE = date(2026, 9, 30)
DEFAULT_SEED = 20261001
DEFAULT_MONTHS = 12
# 主数据（产线、设备、人员等）与种子无关：工厂固定，人员名单供 010 搭飞书测试租户
MASTER_SEED = 20261001


@dataclass(frozen=True)
class Settings:
    months: int = DEFAULT_MONTHS
    seed: int = DEFAULT_SEED

    def __post_init__(self) -> None:
        if not 1 <= self.months <= 12:
            raise ValueError(f"月数须在 1–12 之间，收到 {self.months}")

    def month_list(self) -> list[tuple[int, int]]:
        """从最早的月份到基准日所在月份（含）。"""
        result: list[tuple[int, int]] = []
        year, month = BASE_DATE.year, BASE_DATE.month
        for _ in range(self.months):
            result.append((year, month))
            year, month = (year, month - 1) if month > 1 else (year - 1, 12)
        return list(reversed(result))


def month_rng(seed: int, year: int, month: int) -> random.Random:
    return random.Random(f"{seed}-{year:04d}{month:02d}")  # noqa: S311 仅生成模拟数据
