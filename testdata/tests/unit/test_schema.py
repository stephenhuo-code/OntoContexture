"""表定义：三套系统的表清单（data-model.md 第 3–5 节）、中文说明、三种方言的建表语句。"""

import pytest

from mockfactory.schema import DIALECTS, TABLES, ddl, tables_of

MES = {
    "production_line", "equipment", "equipment_event", "material", "supplier", "material_lot",
    "operation", "team", "employee", "work_order", "production_batch", "operation_report",
    "material_consumption",
}  # fmt: skip
QMS = {
    "customer", "defect_code", "inspection_item", "inspection_record", "inspection_value", "ncr",
    "eight_d",
}  # fmt: skip
DW = {
    "dim_line", "dim_equipment", "dim_product", "dwd_operation_report", "dwd_inspection_value",
    "dwd_ncr", "dws_line_daily_quality", "dws_line_monthly_quality",
}  # fmt: skip


def test_table_lists() -> None:
    assert {t.name for t in tables_of("mes")} == MES
    assert {t.name for t in tables_of("qms")} == QMS
    assert {t.name for t in tables_of("dw")} == DW


def test_every_table_and_column_has_chinese_comment() -> None:
    for table in TABLES:
        assert table.comment, table.name
        assert table.primary_key, table.name
        for column in table.columns:
            assert column.comment, f"{table.name}.{column.name}"
            assert any("一" <= ch <= "鿿" for ch in column.comment)


def test_primary_key_columns_come_first() -> None:
    """Doris 的 UNIQUE KEY 列必须是表的前几列；三套库统一按此约定。"""
    for table in TABLES:
        names = [c.name for c in table.columns]
        assert names[: len(table.primary_key)] == list(table.primary_key), table.name


def test_mysql_ddl() -> None:
    sql = ddl(next(t for t in TABLES if t.name == "equipment"), "mysql")
    assert len(sql) == 1
    assert "CREATE TABLE `equipment`" in sql[0]
    assert "COMMENT '设备'" in sql[0]
    assert "PRIMARY KEY (`equip_code`)" in sql[0]


def test_postgres_ddl_has_comment_statements() -> None:
    table = next(t for t in TABLES if t.name == "ncr")
    sql = ddl(table, "postgres")
    assert sql[0].startswith('CREATE TABLE "ncr"')
    assert 'PRIMARY KEY ("ncr_no")' in sql[0]
    assert any(s.startswith('COMMENT ON TABLE "ncr"') for s in sql)
    assert sum(s.startswith("COMMENT ON COLUMN") for s in sql) == len(table.columns)


def test_doris_ddl() -> None:
    sql = ddl(next(t for t in TABLES if t.name == "dws_line_daily_quality"), "doris")
    assert len(sql) == 1
    assert "UNIQUE KEY(`line_code`, `stat_date`)" in sql[0]
    assert '"replication_num" = "1"' in sql[0]
    assert "COMMENT '" in sql[0]


def test_unknown_dialect() -> None:
    assert set(DIALECTS) == {"mysql", "postgres", "doris"}
    with pytest.raises(ValueError, match="方言"):
        ddl(TABLES[0], "oracle")
