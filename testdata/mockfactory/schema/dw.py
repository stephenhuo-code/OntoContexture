"""模拟数仓（Doris，database `mock_dw`）：维度、明细层（DWD）、汇总层（DWS）。

一次合格率两种口径（C3），均以终检工序报工为准，日期取终检开工日期：
- 帆软报表口径 fpy_incl_rework =（首次合格数 + 返工后合格数）÷ 投入数
- 严格口径 fpy_strict = 首次合格数 ÷ 投入数
"""

from mockfactory.schema.base import Table, table

S = "dw"

_QUALITY = (
    ("input_qty", "int", "终检投入数量"),
    ("first_pass_qty", "int", "首次合格数量"),
    ("rework_ok_qty", "int", "返工后合格数量"),
    ("scrap_qty", "int", "报废数量"),
    ("fpy_incl_rework", "rate", "一次合格率（帆软报表口径：含返工后合格）"),
    ("fpy_strict", "rate", "一次合格率（严格口径：仅首次合格）"),
)

TABLES: list[Table] = [
    table(
        S, "dim_line", "产线维度", ("line_code",),
        ("line_code", "code", "产线编码"),
        ("line_name", "name", "产线名称"),
        ("product_family", "name", "主要产品族"),
    ),
    table(
        S, "dim_equipment", "设备维度", ("equip_code",),
        ("equip_code", "code", "设备编号"),
        ("equip_name", "name", "设备名称"),
        ("equip_type", "name", "设备类型"),
        ("line_code", "code", "所在产线编码"),
        ("op_code", "code", "承担的工序编码"),
    ),
    table(
        S, "dim_product", "产品维度", ("product_code",),
        ("product_code", "code", "产品物料编码"),
        ("product_name", "name", "产品名称"),
        ("line_code", "code", "生产产线编码"),
    ),
    table(
        S, "dwd_operation_report", "报工明细（带产线、产品、班组冗余字段）", ("report_id",),
        ("report_id", "code", "报工编号"),
        ("report_date", "date", "报工日期（开工日期）"),
        ("line_code", "code", "产线编码"),
        ("product_code", "code", "产品物料编码"),
        ("batch_no", "code", "成品批次号"),
        ("wo_no", "code", "工单号"),
        ("op_code", "code", "工序编码"),
        ("is_final_op", "int", "是否终检工序：1 是，0 否"),
        ("equip_code", "code", "设备编号"),
        ("operator_no", "code", "操作工工号"),
        ("team_code", "code", "当班班组编码"),
        ("shift", "name", "班次"),
        ("input_qty", "int", "投入数量"),
        ("good_qty", "int", "首次合格数量"),
        ("rework_qty", "int", "返工后合格数量"),
        ("scrap_qty", "int", "报废数量"),
    ),
    table(
        S, "dwd_inspection_value", "检验实测值明细（带检验类型、批次、工序冗余字段）",
        ("insp_no", "item_code", "sample_seq"),
        ("insp_no", "code", "检验单号"),
        ("item_code", "code", "检验项编码"),
        ("sample_seq", "int", "样本序号"),
        ("insp_date", "date", "检验日期"),
        ("insp_type", "name", "检验类型"),
        ("line_code", "code", "产线编码（来料检验为空）"),
        ("batch_no", "code", "成品批次号"),
        ("lot_no", "code", "物料批次号"),
        ("op_code", "code", "工序编码"),
        ("equip_code", "code", "设备编号"),
        ("measured_value", "dec", "实测值"),
        ("judgement", "name", "单值判定"),
    ),
    table(
        S, "dwd_ncr", "NCR 明细", ("ncr_no",),
        ("ncr_no", "code", "NCR 号"),
        ("found_date", "date", "发现日期"),
        ("source", "name", "来源"),
        ("line_code", "code", "产线编码"),
        ("batch_no", "code", "成品批次号"),
        ("lot_no", "code", "物料批次号"),
        ("product_code", "code", "产品物料编码"),
        ("defect_code", "code", "缺陷码"),
        ("responsible_op", "code", "责任工序编码"),
        ("customer_code", "code", "客户编码"),
        ("qty", "int", "不合格数量"),
    ),
    table(
        S, "dws_line_daily_quality", "产线日质量汇总", ("line_code", "stat_date"),
        ("line_code", "code", "产线编码"),
        ("stat_date", "date", "统计日期（终检开工日期）"),
        *_QUALITY,
    ),
    table(
        S, "dws_line_monthly_quality", "产线月质量汇总（帆软现有报表的数据源）",
        ("line_code", "stat_month"),
        ("line_code", "code", "产线编码"),
        ("stat_month", "code", "统计月份，如 2026-09"),
        *_QUALITY,
    ),
]  # fmt: skip
