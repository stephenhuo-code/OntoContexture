"""verify-cases（Testcontainers）：1 个月规模下 C1、C2 与 C3 明细口径通过；篡改数据后退出码 4。"""

import re

import pymysql
import pytest

from mockfactory.__main__ import main
from mockfactory.load import parse_mysql_dsn

pytestmark = pytest.mark.integration


def test_verify_cases(
    mysql_dsn: str, postgres_dsn: str, capsys: pytest.CaptureFixture[str]
) -> None:
    target = ["--target", "dsn", "--mes", mysql_dsn, "--qms", postgres_dsn]
    assert main(["load", *target, "--months", "1"]) == 0
    capsys.readouterr()
    assert main(["verify-cases", *target]) == 0
    out = capsys.readouterr().out
    for case in ("C1", "C2", "C3"):
        assert case in out
    assert not re.search(r"步骤 \d+ 失败", out)
    assert re.search(r"C3 步骤 3 跳过", out)  # 未提供数仓时，C3 的汇总口径步骤跳过

    conn = pymysql.connect(**parse_mysql_dsn(mysql_dsn), database="mes", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE equipment_event SET alarm_code = 'SP-XXX' WHERE event_id = 'EV2609-0901'"
            )
    finally:
        conn.close()
    assert main(["verify-cases", *target]) == 4
    out = capsys.readouterr().out
    assert re.search(r"C1 步骤 5 失败", out)
    assert "SP-XXX" in out
