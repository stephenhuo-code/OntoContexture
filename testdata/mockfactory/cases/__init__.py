"""3 个案例（均在 2026-09）：在正常数据之后、数仓生成之前注入。"""

from mockfactory.cases import c1_equipment, c2_material, c3_fpy
from mockfactory.generate.draft import Draft

CASE_MONTH = (2026, 9)


def apply(d: Draft) -> None:
    if (d.year, d.month) != CASE_MONTH:
        return
    c1_equipment.apply(d)
    c2_material.apply(d)
    c3_fpy.apply(d)
