"""C2 来料不良追溯（P1）：供应商 S03 的一个毛坯批次硬度偏下限，热处理后出现裂纹。

该物料批次投料到 1 号线的 6 个工单，其中 4 个批次在终检磁粉探伤发现裂纹，另 2 个尚未发现问题。
参数固定，不随种子变化；标准答案见 testdata/cases/C2.yaml。
"""

from datetime import datetime
from decimal import Decimal

from mockfactory.generate.draft import Draft

LOT = "ML260902-901"
RECEIVED = datetime(2026, 9, 2, 10, 0)
HARDNESS = ["28.4", "28.7", "28.3", "28.9", "28.5"]  # HRC，合格区间 28–34，处于下限附近
BATCHES = [
    "B260915-L1-01", "B260915-L1-02", "B260916-L1-01", "B260916-L1-02", "B260917-L1-01",
    "B260917-L1-02",
]  # fmt: skip
# 终检磁粉探伤：每件 0 无裂纹、1 有裂纹
CRACKS = {
    "B260915-L1-01": [0, 1, 0, 0, 1],
    "B260915-L1-02": [1, 0, 0, 0, 0],
    "B260916-L1-01": [0, 0, 1, 0, 1],
    "B260917-L1-01": [1, 1, 0, 0, 0],
}
SCRAP_PER_BATCH = 4  # 发现裂纹后全检报废


def apply(d: Draft) -> None:
    d.add(
        "material_lot", lot_no=LOT, material_code="M-FG-110", supplier_code="S03",
        supplier_lot_no="SL-S03-260828", received_at=RECEIVED, qty=300,
    )  # fmt: skip
    d.add(
        "inspection_record", insp_no="IL2609-0901", insp_type="来料", batch_no=None, lot_no=LOT,
        op_code=None, equip_code=None, inspected_at=datetime(2026, 9, 2, 12, 0),
        inspector_no="E0061", sample_qty=5, result="合格",
    )  # fmt: skip
    for i, value in enumerate(HARDNESS, start=1):
        d.add(
            "inspection_value", insp_no="IL2609-0901", item_code="I-FG-HRC", sample_seq=i,
            measured_value=Decimal(value), judgement="合格",
        )  # fmt: skip
    for batch in BATCHES:
        d.one("material_consumption", batch_no=batch, material_code="M-FG-110")["lot_no"] = LOT
    for batch, cracks in CRACKS.items():
        rec = d.one("inspection_record", batch_no=batch, op_code="L1-OP80")
        for v in d.find("inspection_value", insp_no=rec["insp_no"], item_code="I-L1-MT"):
            v["measured_value"] = Decimal(cracks[v["sample_seq"] - 1])
            v["judgement"] = "不合格" if v["measured_value"] else "合格"
        rec["result"] = "不合格"
        report = d.one("operation_report", batch_no=batch, op_code="L1-OP80")
        report["rework_qty"], report["scrap_qty"] = 0, SCRAP_PER_BATCH
        report["good_qty"] = report["input_qty"] - SCRAP_PER_BATCH
    d.add(
        "ncr", ncr_no="NCR-2609-0902", source="内部", batch_no="B260917-L1-01", lot_no=LOT,
        product_code="P-OS-100", defect_code="D301", qty=len(CRACKS) * SCRAP_PER_BATCH,
        found_at=datetime(2026, 9, 18, 9, 0), reported_by="E0062", responsible_op=None,
        customer_code=None, status="处理中",
        description="终检磁粉探伤 09-15—09-17 连续 4 批发现裂纹，"
        "怀疑毛坯批次 ML260902-901 硬度偏低",
    )  # fmt: skip
    d.add(
        "eight_d", report_no="8D-2609-0902", ncr_no="NCR-2609-0902", leader_no="E0080",
        root_cause_category="料",
        root_cause="S03 毛坯批次 SL-S03-260828 锻后冷却过快，硬度偏下限，热处理后产生淬火裂纹",
        containment="冻结物料批次 ML260902-901 的全部流向（6 个工单），"
        "对尚未发现问题的 2 个批次全检磁粉探伤",
        corrective_action="S03 提交 8D；毛坯来料硬度抽样由 5 件增至 13 件，增加 29 HRC 预警值",
        opened_at=datetime(2026, 9, 18, 10, 0), closed_at=None, status="进行中",
    )  # fmt: skip
