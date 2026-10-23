# Data Model: 003 模拟工厂数据集与模拟源系统

字段级定义（类型、中文说明）由 `testdata/mockfactory/schema/` 生成到 `testdata/数据说明.md`（以它为准）；本文件定工厂组成、表、
关键字段、跨系统关联键、规模与案例。

## 1. 工厂组成

| 项 | 内容 |
| --- | --- |
| 工厂 | 1 家汽车零部件厂（合成名称） |
| 产线 | L1 1 号线：输出轴总成（机加工 + 装配）；L2 2 号线：法兰盘（机加工为主） |
| 设备 | 每条线约 10 台：数控车床、加工中心、磨床、热处理炉、清洗机、装配压机、检测台等，共约 20 台 |
| 工序 | 每条线 6–8 道：下料 / 粗车 / 精车 / 铣键槽 / 热处理 / 磨削 / （装配）/ 终检 |
| 班组与班次 | 每条线甲、乙两班（白班、夜班），每班 1 个班组，另有质检组、设备维修组 |
| 人员 | 约 80 人：操作工、班组长、工艺工程师、质量工程师、检验员、设备维修工、供应商质量工程师 |
| 物料 | 毛坯（锻件、棒料）、外购件（轴承、密封圈）、成品各若干；供应商 6 家 |
| 客户 | 3 家整车厂（合成名称） |

## 2. 编号规则（跨系统关联键）

| 编号 | 格式示例 | 出现在 |
| --- | --- | --- |
| 产线 | `L1`、`L2` | MES、QMS、数仓 |
| 设备编号 | `L2-CNC-03` | MES、QMS（过程检验）、数仓 |
| 工序编码 | `L2-OP30` | MES、QMS、数仓 |
| 工号 | `E0123` | MES（报工）、QMS（检验员、8D 组长）、名单（飞书） |
| 班组 | `L2-B`（2 号线乙班） | MES、名单（飞书） |
| 工单号 | `WO2609-0412` | MES、数仓 |
| 成品批次号 | `B260911-L2-03` | MES、QMS、数仓 |
| 物料批次号 | `ML260902-017`；供应商批次 `SL-xxxxx` | MES（投料）、QMS（来料检验） |
| NCR 号 | `NCR-2609-0007` | QMS |
| 8D 报告号 | `8D-2609-0003` | QMS |

## 3. MES（MySQL，database `mes`）

| 表 | 含义 | 关键字段 |
| --- | --- | --- |
| `production_line` | 产线 | line_code, name, product_family |
| `equipment` | 设备 | equip_code, name, type, model, line_code, op_code, installed_on |
| `equipment_event` | 设备事件（保养、报警、预警、停机、维修） | event_id, equip_code, event_time, event_type, alarm_code, description, handled_by |
| `material` | 物料（毛坯、外购件、成品） | material_code, name, category, spec, unit |
| `supplier` | 供应商 | supplier_code, name |
| `material_lot` | 物料批次 | lot_no, material_code, supplier_code, supplier_lot_no, received_at, qty |
| `operation` | 工序定义（工艺路线） | op_code, line_code, seq, name, equip_type, std_cycle_sec |
| `team` | 班组 | team_code, name, line_code, shift |
| `employee` | 人员 | emp_no, name, position, team_code, hired_on |
| `work_order` | 工单 | wo_no, product_code, line_code, plan_qty, planned_start, status |
| `production_batch` | 成品批次 | batch_no, wo_no, product_code, line_code, qty, started_at, finished_at |
| `operation_report` | 工序报工 | report_id, batch_no, op_code, equip_code, operator_no, team_code, shift, started_at, ended_at, input_qty, good_qty, rework_qty, scrap_qty |
| `material_consumption` | 投料 | id, wo_no, batch_no, lot_no, qty, consumed_at |

## 4. QMS（PostgreSQL，database `qms`）

| 表 | 含义 | 关键字段 |
| --- | --- | --- |
| `customer` | 客户 | customer_code, name |
| `defect_code` | 缺陷码（两级） | code, name, category, parent_code |
| `inspection_item` | 检验项（含公差） | item_code, name, target, lower_limit, upper_limit, unit, op_code / material_code |
| `inspection_record` | 检验单（来料、过程、终检） | insp_no, insp_type, batch_no / lot_no, op_code, equip_code, inspected_at, inspector_no, sample_qty, result |
| `inspection_value` | 检验实测值 | insp_no, item_code, sample_seq, measured_value, judgement |
| `ncr` | 不合格报告（客诉、内部、来料） | ncr_no, source, batch_no / lot_no, product_code, defect_code, qty, found_at, reported_by, responsible_op, customer_code, status, description |
| `eight_d` | 8D 历史 | report_no, ncr_no, leader_no, root_cause_category, root_cause, containment, corrective_action, opened_at, closed_at, status |

## 5. 数仓（Doris，database `mock_dw`）

| 表 | 层 | 含义 |
| --- | --- | --- |
| `dim_equipment`、`dim_product`、`dim_line` | 维度 | 设备、产品、产线维度 |
| `dwd_operation_report` | 明细 | 报工明细（带产线、产品、班组冗余字段） |
| `dwd_inspection_value` | 明细 | 检验实测值明细（带检验类型、批次、工序冗余字段） |
| `dwd_ncr` | 明细 | NCR 明细 |
| `dws_line_daily_quality` | 汇总 | 产线 × 日：投入数、首次合格数、返工后合格数、报废数、两种口径的一次合格率 |
| `dws_line_monthly_quality` | 汇总 | 产线 × 月：同上（帆软现有报表的数据源） |

一次合格率两种口径（C3）：

- **帆软报表口径**（`fpy_incl_rework`）=（首次合格数 + 返工后合格数）÷ 投入数
- **严格口径**（`fpy_strict`）= 首次合格数 ÷ 投入数

均以终检工序的报工为准；汇总层的数值必须能由明细层重算得到。

## 6. 规模（默认 12 个月，实测）

| 系统 | 主要表 | 每月约（30 天） | 12 个月 |
| --- | --- | --- | --- |
| MES | 工单 / 批次（每线每天 20 批） | 1,200 / 1,200 | 14,600 / 14,600 |
| MES | 工序报工 | 8,400 | 102,200 |
| MES | 投料、设备事件、物料批次 | 2,400、115、16 | 29,200、1,388、192 |
| QMS | 检验单 / 实测值 | 3,600 / 30,000 | 43,944 / 365,720 |
| QMS | NCR / 8D | 23 / 7 | 281 / 84 |
| 数仓 | DWD 明细 | 38,500 | 468,201 |
| 数仓 | DWS 汇总、维度 | 62、23 | 754、23 |
| **合计** | | **约 8.6 万** | **1,041,352** |

最小规模（1 个月，2026-09）85,770 行，用于集成测试。主数据（产线、设备、人员等）与规模、种子无关。
实测磁盘占用：MES 约 50 MB、QMS 约 58 MB，Doris 为压缩列存（更小）。

## 7. 案例（全部在 2026-09）

| 案例 | 注入的记录 | 标准答案文件 |
| --- | --- | --- |
| C1 设备故障 | `L2-CNC-03`：09-08 10:15 振动预警（无人处理）、09-12 02:30 主轴异响停机、09-12 09:30 维修；09-11 凌晨乙班（操作工 E0047）在该设备精车的 3 个批次 `B260911-L2-02/03/04`，精车外径偏大（10 个样本超 80.020）；终检公差误设为 ±0.03 而放行；09-22 客诉 `NCR-2609-0901`（客户 C02）与 8D | `testdata/cases/C1.yaml` |
| C2 来料不良 | 供应商 S03 的毛坯批次 `ML260902-901`（来料硬度 28.3–28.9 HRC，下限 28）；投料到 1 号线 09-15—09-17 的 6 个工单；其中 4 批终检磁粉探伤发现裂纹，09-18 开内部 `NCR-2609-0902`；另 2 批尚未发现问题 | `testdata/cases/C2.yaml` |
| C3 口径分歧 | 2 号线 2026-09 共 600 批、终检投入 60,000 件，返工后合格 720、报废 67（按固定规律注入）；帆软口径一次合格率 0.9989，严格口径 0.9869 | `testdata/cases/C3.yaml` |

案例使用的 NCR、8D、设备事件、物料批次、来料检验单编号从 `0901` / `901` 起，正常数据不占用。

正常数据的约束（避免与案例混淆）：关键尺寸在公差带中部、来料硬度在合格区间中段、设备事件只有计划保养与一般报警
（无主轴类预警）、NCR 不使用案例的“缺陷码 + 责任工序”组合（D101 + L2-OP30）与缺陷码 D301。
2 号线只在终检返工与报废，且排程固定（每线每天 20 批、开工时间固定、当天完工），因此案例的批次号、工单号与 C3 的数值
与种子、规模无关。

## 8. 案例答案文件结构

见 [contracts/case-answer.schema.json](contracts/case-answer.schema.json)：案例编号、场景、故事、入口编号、逐步查询（说明、
目标系统、SQL、期望结果）。答案与规模无关。
