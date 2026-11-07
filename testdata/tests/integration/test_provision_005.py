"""005 测试数据（真实 MySQL 8.4 / PostgreSQL 17，Testcontainers）：只读元数据账号与 viewlab 视图测试库。

- 只读账号能看到库 / 表 / 字段，不能写；003 的 mes、qms 不受影响（本模块不重建它们）。
- viewlab：可读账号能读视图定义；MySQL 受限账号（无 SHOW VIEW）读不到；视图与基表关系与标准答案一致。
"""

import asyncio
from urllib.parse import urlparse

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import pymysql
import pytest

from mockfactory.load import parse_mysql_dsn
from mockfactory.viewlab import (
    ACCOUNTS,
    DATABASE,
    LINEAGE,
    TABLES,
    VIEWS,
    provision_mysql,
    provision_postgres,
)

pytestmark = pytest.mark.integration

PASSWORDS = {name: f"pw-{name}" for name in ACCOUNTS}


def _mysql(dsn: str, user: str | None = None, database: str | None = None) -> "pymysql.Connection":
    params = parse_mysql_dsn(dsn)
    if user:
        params = {**params, "user": user, "password": PASSWORDS[user]}
    return pymysql.connect(**params, database=database, autocommit=True)


def _pg_dsn(dsn: str, database: str, user: str | None = None) -> str:
    p = urlparse(dsn)
    netloc = p.netloc if user is None else f"{user}:{PASSWORDS[user]}@{p.hostname}:{p.port}"
    return p._replace(netloc=netloc, path=f"/{database}").geturl()


async def _pg_fetch(dsn: str, sql: str) -> list[tuple[object, ...]]:
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        return [tuple(r) for r in await conn.fetch(sql)]
    finally:
        await conn.close()


def pg_fetch(dsn: str, sql: str) -> list[tuple[object, ...]]:
    return asyncio.run(_pg_fetch(dsn, sql))


def test_mysql_readonly_and_viewlab(mysql_dsn: str) -> None:
    admin = _mysql(mysql_dsn)
    with admin.cursor() as cur:
        cur.execute("CREATE DATABASE IF NOT EXISTS mes")
        cur.execute("CREATE TABLE IF NOT EXISTS mes.probe (id INT PRIMARY KEY)")
    provision_mysql(parse_mysql_dsn(mysql_dsn), PASSWORDS)
    provision_mysql(parse_mysql_dsn(mysql_dsn), PASSWORDS)  # 幂等

    ro = _mysql(mysql_dsn, "mes_meta_ro")
    with ro.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='mes' AND table_name='probe'"
        )
        assert cur.fetchall() == (("id",),)
        with pytest.raises(pymysql.err.MySQLError):
            cur.execute("INSERT INTO mes.probe VALUES (1)")

    lab = _mysql(mysql_dsn, "viewlab_ro", DATABASE)
    with lab.cursor() as cur:
        cur.execute(
            "SELECT table_name, table_type FROM information_schema.tables "
            "WHERE table_schema=%s ORDER BY table_name",
            (DATABASE,),
        )
        found = dict(cur.fetchall())
        assert {t: "BASE TABLE" for t in TABLES} | {v: "VIEW" for v in VIEWS} == found
        cur.execute(
            "SELECT table_name, view_definition FROM information_schema.views WHERE table_schema=%s",
            (DATABASE,),
        )
        definitions = dict(cur.fetchall())
        for view, upstream in LINEAGE.items():
            for table in upstream["tables"]:
                assert table in definitions[view]
        with pytest.raises(pymysql.err.MySQLError):
            cur.execute("DELETE FROM supplier")

    restricted = _mysql(mysql_dsn, "viewlab_noview", DATABASE)
    with restricted.cursor() as cur:
        cur.execute(
            "SELECT view_definition FROM information_schema.views WHERE table_schema=%s",
            (DATABASE,),
        )
        assert all(not row[0] for row in cur.fetchall())
        with pytest.raises(pymysql.err.MySQLError):
            cur.execute("SHOW CREATE VIEW v_supplier_orders")


def test_postgres_readonly_and_viewlab(postgres_dsn: str) -> None:
    async def create_qms() -> None:
        conn = await asyncpg.connect(postgres_dsn, timeout=10)
        try:
            exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname='qms'")
            if not exists:
                await conn.execute('CREATE DATABASE "qms"')
        finally:
            await conn.close()
        qms = await asyncpg.connect(_pg_dsn(postgres_dsn, "qms"), timeout=10)
        try:
            await qms.execute("CREATE TABLE IF NOT EXISTS probe (id INT PRIMARY KEY)")
        finally:
            await qms.close()

    asyncio.run(create_qms())
    provision_postgres(postgres_dsn, PASSWORDS)
    provision_postgres(postgres_dsn, PASSWORDS)  # 幂等

    ro = _pg_dsn(postgres_dsn, "qms", "qms_meta_ro")
    assert pg_fetch(
        ro, "SELECT column_name FROM information_schema.columns WHERE table_name='probe'"
    ) == [("id",)]
    with pytest.raises(asyncpg.PostgresError):
        pg_fetch(ro, "INSERT INTO probe VALUES (1) RETURNING id")

    lab = _pg_dsn(postgres_dsn, DATABASE, "viewlab_ro")
    rows = pg_fetch(
        lab,
        "SELECT table_name, table_type FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name",
    )
    assert dict(rows) == {t: "BASE TABLE" for t in TABLES} | {v: "VIEW" for v in VIEWS}
    for view, upstream in LINEAGE.items():
        definition = str(pg_fetch(lab, f"SELECT pg_get_viewdef('{view}'::regclass)")[0][0])
        for table in upstream["tables"]:
            assert table in definition
    with pytest.raises(asyncpg.PostgresError):
        pg_fetch(lab, "DELETE FROM supplier RETURNING 1")
