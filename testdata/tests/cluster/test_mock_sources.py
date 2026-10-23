"""本地集群（make up 之后）：模拟 MES、QMS 可连接；Doris 中 mock_dw 与只读账号；
load --target local 后行数一致。"""

import pymysql
import pytest
from conftest_data import dataset

from mockfactory.__main__ import main
from mockfactory.load import local_targets

pytestmark = pytest.mark.cluster


def test_local_load(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["load", "--target", "local", "--months", "1"]) == 0
    out = capsys.readouterr().out
    for system in ("mes", "qms", "dw"):
        assert system in out
    ds = dataset()
    with local_targets() as targets:
        assert targets.mes is not None
        mes = pymysql.connect(**targets.mes, database="mes")
        try:
            with mes.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM operation_report")
                assert cur.fetchone() == (ds.count("operation_report"),)
        finally:
            mes.close()
        assert targets.dw is not None
        assert targets.dw_reader_password
        reader = pymysql.connect(
            host=targets.dw["host"],
            port=targets.dw["port"],
            user="mock_dw_reader",
            password=targets.dw_reader_password,
            database="mock_dw",
        )
        try:
            with reader.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM dws_line_monthly_quality")
                assert cur.fetchone() == (ds.count("dws_line_monthly_quality"),)
                with pytest.raises(pymysql.err.MySQLError):
                    cur.execute("DELETE FROM dim_line WHERE line_code = 'L1'")
        finally:
            reader.close()
