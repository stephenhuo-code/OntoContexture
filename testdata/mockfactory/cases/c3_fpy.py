"""C3 一次合格率口径分歧（P2）：2 号线 2026-09 终检的返工与报废按固定规律注入。

2 号线终检投入恒为每批 100 件、每月 600 批，因此两种口径的月度一次合格率与种子无关：
帆软报表口径（含返工后合格）0.9989，严格口径 0.9869。标准答案见 testdata/cases/C3.yaml。
"""

from mockfactory.generate.draft import Draft

REWORK = [4, 0, 2, 0, 1, 0, 3, 0, 0, 2]  # 按批次顺序循环


def apply(d: Draft) -> None:
    finals = sorted(d.find("operation_report", op_code="L2-OP60"), key=lambda r: r["batch_no"])
    for k, r in enumerate(finals):
        r["rework_qty"] = REWORK[k % len(REWORK)]
        r["scrap_qty"] = 1 if k % 9 == 4 else 0
        r["good_qty"] = r["input_qty"] - r["rework_qty"] - r["scrap_qty"]
