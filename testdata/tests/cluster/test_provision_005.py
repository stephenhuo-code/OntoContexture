"""本地集群（make mock-data 之后）：005 只读元数据账号与 viewlab 视图测试库已就绪。"""

import pymysql
import pytest

from mockfactory.load import local_targets
from mockfactory.viewlab import DATABASE, TABLES, VIEWS, local_passwords

pytestmark = pytest.mark.cluster


def test_cluster_readonly_accounts_and_viewlab() -> None:
    passwords = local_passwords()
    with local_targets() as targets:
        assert targets.mes is not None
        host, port = targets.mes["host"], targets.mes["port"]
        ro = pymysql.connect(
            host=host, port=port, user="mes_meta_ro", password=passwords["mes_meta_ro"]
        )
        try:
            with ro.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='mes'"
                )
                assert cur.fetchone() == (13,)  # 003 金标准：MES 13 张表
                with pytest.raises(pymysql.err.MySQLError):
                    cur.execute("DELETE FROM mes.operation_report")
        finally:
            ro.close()
        lab = pymysql.connect(
            host=host,
            port=port,
            user="viewlab_ro",
            password=passwords["viewlab_ro"],
            database=DATABASE,
        )
        try:
            with lab.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
                    (DATABASE,),
                )
                assert {r[0] for r in cur.fetchall()} == set(TABLES) | set(VIEWS)
        finally:
            lab.close()
