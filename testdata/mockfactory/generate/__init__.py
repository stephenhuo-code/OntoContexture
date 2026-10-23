"""生成总入口：主数据一次，之后按月生成（生产 → 质量与设备事件 →（案例）→ 数仓），写入顺序固定。"""

from mockfactory import cases as case_modules
from mockfactory.config import Settings, month_rng
from mockfactory.dataset import Dataset
from mockfactory.generate import production, quality, warehouse
from mockfactory.generate.draft import Draft
from mockfactory.generate.master import add_master, build_master


def build(settings: Settings, cases: bool = True) -> Dataset:
    ds = Dataset()
    m = build_master()
    add_master(ds, m)
    warehouse.add_dims(ds, m)
    for year, month in settings.month_list():
        rng = month_rng(settings.seed, year, month)
        d = Draft(year, month)
        production.generate_month(d, m, rng)
        quality.generate_month(d, m, rng)
        if cases:
            case_modules.apply(d)
        warehouse.generate_month(d, m)
        d.flush(ds)
    return ds
