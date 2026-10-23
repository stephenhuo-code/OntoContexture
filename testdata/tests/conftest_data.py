"""单元测试共用的生成结果（按参数缓存，避免重复生成）。"""

from functools import cache

from mockfactory.config import Settings
from mockfactory.dataset import Dataset
from mockfactory.generate import build


@cache
def dataset(months: int = 1, seed: int = 20261001, cases: bool = True) -> Dataset:
    return build(Settings(months=months, seed=seed), cases=cases)
