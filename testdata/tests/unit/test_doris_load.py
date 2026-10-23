"""Doris 写入：以记录 SQL 的假连接验证语句（集群测试之外，CI 中也覆盖 load/doris.py）。"""

from types import TracebackType
from typing import Any

import pytest
from conftest_data import dataset

from mockfactory.load.doris import BATCH_SIZE, load_doris
from mockfactory.schema import tables_of


class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    def execute(self, sql: str, args: Any = None) -> None:
        self.conn.statements.append(sql)

    def executemany(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if self.conn.fail_on_insert:
            raise RuntimeError("写入失败")
        self.conn.inserts.append((sql, len(rows)))


class FakeConn:
    def __init__(self, fail_on_insert: bool = False) -> None:
        self.statements: list[str] = []
        self.inserts: list[tuple[str, int]] = []
        self.fail_on_insert = fail_on_insert

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


def test_statements() -> None:
    ds = dataset()
    conn = FakeConn()
    load_doris(conn, ds, reader_password="secret-x")
    assert conn.statements[0] == "DROP DATABASE IF EXISTS `mock_dw` FORCE"
    assert conn.statements[1] == "CREATE DATABASE `mock_dw`"
    creates = [s for s in conn.statements if s.startswith("CREATE TABLE")]
    assert len(creates) == len(tables_of("dw")) == 8
    assert all("UNIQUE KEY(" in s and '"replication_num" = "1"' in s for s in creates)
    for table in tables_of("dw"):
        inserted = [n for sql, n in conn.inserts if f"INSERT INTO `mock_dw`.`{table.name}`" in sql]
        assert sum(inserted) == ds.count(table.name)
        assert all(n <= BATCH_SIZE for n in inserted)
    assert BATCH_SIZE == 1000
    assert any("CREATE USER IF NOT EXISTS 'mock_dw_reader'@'%'" in s for s in conn.statements)
    assert "GRANT SELECT_PRIV ON internal.mock_dw.* TO 'mock_dw_reader'@'%'" in conn.statements


def test_no_reader_without_password() -> None:
    conn = FakeConn()
    load_doris(conn, dataset(), reader_password=None)
    assert not any("mock_dw_reader" in s for s in conn.statements)


def test_failure_drops_database() -> None:
    conn = FakeConn(fail_on_insert=True)
    with pytest.raises(RuntimeError):
        load_doris(conn, dataset(), reader_password=None)
    assert conn.statements[-1] == "DROP DATABASE IF EXISTS `mock_dw` FORCE"
