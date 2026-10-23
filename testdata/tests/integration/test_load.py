"""写入 MySQL、PostgreSQL（Testcontainers）：表与字段注释、行数、摘要可复现、
目标不可连接时退出码 2。"""

import pymysql
import pytest
from conftest_data import dataset

from mockfactory.__main__ import main
from mockfactory.checksum import dataset_checksums, format_checksums
from mockfactory.load import parse_mysql_dsn

pytestmark = pytest.mark.integration


def _args(mysql_dsn: str, postgres_dsn: str) -> list[str]:
    return ["--target", "dsn", "--mes", mysql_dsn, "--qms", postgres_dsn, "--months", "1"]


def test_load_and_checksum(
    mysql_dsn: str, postgres_dsn: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["load", *_args(mysql_dsn, postgres_dsn)]) == 0
    out = capsys.readouterr().out
    assert "operation_report" in out

    conn = pymysql.connect(**parse_mysql_dsn(mysql_dsn), database="mes")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = 'mes' AND column_comment = ''"
            )
            assert cur.fetchone() == (0,)
            cur.execute("SELECT COUNT(*) FROM operation_report")
            assert cur.fetchone() == (dataset().count("operation_report"),)
    finally:
        conn.close()

    assert main(["checksum", *_args(mysql_dsn, postgres_dsn)]) == 0
    first = capsys.readouterr().out
    expected = format_checksums(
        {k: v for k, v in dataset_checksums(dataset()).items() if k[0] != "dw"}
    )
    assert first.strip() == expected.strip()

    assert main(["load", *_args(mysql_dsn, postgres_dsn)]) == 0
    capsys.readouterr()
    assert main(["checksum", *_args(mysql_dsn, postgres_dsn)]) == 0
    assert capsys.readouterr().out == first


def test_unreachable_target_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "load", "--target", "dsn", "--months", "1",
            "--mes", "mysql://root:x@127.0.0.1:1",
            "--qms", "postgresql://postgres:x@127.0.0.1:1/postgres",
        ]
    )  # fmt: skip
    assert code == 2
    assert "未就绪" in capsys.readouterr().err
