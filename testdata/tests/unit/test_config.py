"""配置：固定基准日、规模（月数）校验、按月独立的随机流。"""

from datetime import date

import pytest

from mockfactory.config import BASE_DATE, DEFAULT_SEED, Settings, month_rng


def test_base_date_and_default_seed() -> None:
    assert date(2026, 9, 30) == BASE_DATE
    assert DEFAULT_SEED == 20261001
    assert Settings().months == 12


@pytest.mark.parametrize("months", [0, 13, -1])
def test_months_out_of_range(months: int) -> None:
    with pytest.raises(ValueError, match="1–12"):
        Settings(months=months)


def test_month_list_ends_at_base_month() -> None:
    assert Settings(months=1).month_list() == [(2026, 9)]
    months = Settings(months=12).month_list()
    assert months[0] == (2025, 10)
    assert months[-1] == (2026, 9)
    assert len(months) == 12


def test_month_rng_is_stable_and_independent() -> None:
    a = [month_rng(1, 2026, 9).random() for _ in range(3)]
    b = [month_rng(1, 2026, 9).random() for _ in range(3)]
    assert a == b
    assert a != [month_rng(1, 2026, 8).random() for _ in range(3)]
    assert a != [month_rng(2, 2026, 9).random() for _ in range(3)]
