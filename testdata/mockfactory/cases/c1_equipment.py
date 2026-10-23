"""C1 设备故障追溯（P1）：L2-CNC-03 主轴前轴承磨损，2026-09-11 凌晨乙班精车的
3 个批次外径偏大，客户退货。

参数固定，不随种子变化；标准答案见 testdata/cases/C1.yaml。
"""

from datetime import datetime
from decimal import Decimal

from mockfactory.generate.draft import Draft

EQUIP = "L2-CNC-03"
SPARE = "L2-CNC-02"
OPERATOR = "E0047"  # 2 号线乙班操作工
INSPECTOR = "E0066"  # 质检乙班
BATCHES = ["B260911-L2-02", "B260911-L2-03", "B260911-L2-04"]
# 精车外径 Ø80 ±0.02：逐批偏大
OD_PROCESS = {
    "B260911-L2-02": ["80.016", "80.019", "80.021", "80.018", "80.022"],
    "B260911-L2-03": ["80.019", "80.023", "80.020", "80.024", "80.021"],
    "B260911-L2-04": ["80.022", "80.026", "80.024", "80.027", "80.025"],
}
# 终检外径公差误设为 ±0.03（图纸为 ±0.02），因此终检放行
OD_FINAL = {
    "B260911-L2-02": ["80.018", "80.020", "80.019", "80.021", "80.017"],
    "B260911-L2-03": ["80.021", "80.023", "80.022", "80.020", "80.024"],
    "B260911-L2-04": ["80.025", "80.027", "80.026", "80.028", "80.024"],
}
WINDOW = (datetime(2026, 9, 11), datetime(2026, 9, 12, 9, 30))  # 至维修完成


def _set_values(d: Draft, insp_no: str, item: str, values: list[str], upper: Decimal) -> bool:
    bad = False
    for v in d.find("inspection_value", insp_no=insp_no, item_code=item):
        value = Decimal(values[v["sample_seq"] - 1])
        v["measured_value"] = value
        v["judgement"] = "不合格" if value > upper else "合格"
        bad = bad or value > upper
    return bad


def apply(d: Draft) -> None:
    # 窗口内精车只有这 3 批在 L2-CNC-03 上；其余改到 L2-CNC-02（含停机至维修期间）
    for r in d.find("operation_report", op_code="L2-OP30"):
        if not WINDOW[0] <= r["started_at"] < WINDOW[1]:
            continue
        if r["batch_no"] in BATCHES:
            r["equip_code"], r["operator_no"] = EQUIP, OPERATOR
        else:
            r["equip_code"] = SPARE
        for rec in d.find("inspection_record", batch_no=r["batch_no"], op_code="L2-OP30"):
            rec["equip_code"] = r["equip_code"]
    for batch in BATCHES:
        rec = d.one("inspection_record", batch_no=batch, op_code="L2-OP30")
        rec["inspector_no"] = INSPECTOR
        bad = _set_values(d, rec["insp_no"], "I-L2-OD80", OD_PROCESS[batch], Decimal("80.020"))
        rec["result"] = "不合格" if bad else "合格"
        final = d.one("inspection_record", batch_no=batch, op_code="L2-OP60")
        _set_values(d, final["insp_no"], "I-L2-OD80F", OD_FINAL[batch], Decimal("80.030"))
    for event_id, ts, kind, alarm, text, handler in (
        (
            "EV2609-0901",
            datetime(2026, 9, 8, 10, 15),
            "预警",
            "SP-VIB",
            "主轴振动 4.8 mm/s，超过预警阈值 4.5 mm/s",
            None,
        ),
        (
            "EV2609-0902",
            datetime(2026, 9, 12, 2, 30),
            "停机",
            "SP-STOP",
            "主轴异响，设备停机",
            "E0072",
        ),
        (
            "EV2609-0903",
            datetime(2026, 9, 12, 9, 30),
            "维修",
            None,
            "更换主轴前轴承，复测振动 1.2 mm/s",
            "E0072",
        ),
    ):
        d.add(
            "equipment_event", event_id=event_id, equip_code=EQUIP, event_time=ts, event_type=kind,
            alarm_code=alarm, description=text, handled_by=handler,
        )  # fmt: skip
    d.add(
        "ncr", ncr_no="NCR-2609-0901", source="客诉", batch_no="B260911-L2-03", lot_no=None,
        product_code="P-FL-200", defect_code="D101", qty=37, found_at=datetime(2026, 9, 22, 14, 30),
        reported_by="E0077", responsible_op="L2-OP30", customer_code="C02", status="处理中",
        description="客户来料检验发现法兰盘外径超差（实测 80.023–80.027，图纸 Ø80 ±0.02），"
        "涉及批次 B260911-L2-02、B260911-L2-03、B260911-L2-04",
    )  # fmt: skip
    d.add(
        "eight_d", report_no="8D-2609-0901", ncr_no="NCR-2609-0901", leader_no="E0078",
        root_cause_category="机",
        root_cause="L2-CNC-03 主轴前轴承磨损，精车外径逐步偏大；09-08 的振动预警未处理；"
        "终检外径公差误设为 ±0.03",
        containment="隔离 3 个批次的库存与在途产品，全检外径",
        corrective_action="更换主轴轴承；振动预警接入停机；终检公差按图纸改为 ±0.02",
        opened_at=datetime(2026, 9, 22, 16, 30), closed_at=None, status="进行中",
    )  # fmt: skip
