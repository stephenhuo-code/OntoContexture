"""其他特性的集成测试：1 个月规模（含 3 个案例）30 秒内载入空的 MySQL、PostgreSQL（SC-005）。"""

import time

import pymysql
import pytest

from mockfactory.load import parse_mysql_dsn
from mockfactory.load.postgres import query
from mockfactory.schema import tables_of
from mockfactory.testing import load_small

pytestmark = pytest.mark.integration


def test_load_small_within_30s(mysql_dsn: str, postgres_dsn: str) -> None:
    started = time.monotonic()
    ds = load_small(mysql_dsn, postgres_dsn)
    assert time.monotonic() - started <= 30
    assert ds.total() > 50_000

    conn = pymysql.connect(**parse_mysql_dsn(mysql_dsn), database="mes")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'mes'")
            assert cur.fetchone() == (len(tables_of("mes")),)
            cur.execute("SELECT COUNT(*) FROM material_lot WHERE lot_no = 'ML260902-901'")
            assert cur.fetchone() == (1,)
    finally:
        conn.close()
    ncrs = query(
        postgres_dsn, "SELECT ncr_no FROM ncr WHERE ncr_no LIKE 'NCR-2609-090%' ORDER BY ncr_no"
    )
    assert [r[0] for r in ncrs] == ["NCR-2609-0901", "NCR-2609-0902"]
