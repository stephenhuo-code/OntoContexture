"""写入模拟 QMS（PostgreSQL）：重建 database `qms`、建表与注释、COPY；失败时清空。"""

import asyncio
from typing import Any
from urllib.parse import urlparse

import asyncpg  # pyright: ignore[reportMissingTypeStubs]

from mockfactory.dataset import Dataset
from mockfactory.schema import ddl, tables_of

DATABASE = "qms"


def _disconnect(conn: asyncpg.Connection) -> None:
    """直接断开而不发送 Terminate：经 kubectl port-forward 时，正常关闭会使服务端重置连接，
    kubectl 随之退出整个端口转发（kubectl 1.36 仍如此）。"""
    conn.terminate()


def database_dsn(admin_dsn: str) -> str:
    return urlparse(admin_dsn)._replace(path=f"/{DATABASE}").geturl()


async def _recreate(admin_dsn: str) -> None:
    admin = await asyncpg.connect(admin_dsn, timeout=5)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{DATABASE}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{DATABASE}"')
    finally:
        _disconnect(admin)


async def _load(admin_dsn: str, ds: Dataset) -> None:
    await _recreate(admin_dsn)
    try:
        conn = await asyncpg.connect(database_dsn(admin_dsn), timeout=5)
        try:
            for t in tables_of(DATABASE):
                for stmt in ddl(t, "postgres"):
                    await conn.execute(stmt)
                await conn.copy_records_to_table(
                    t.name, records=ds.rows[t.name], columns=list(t.column_names)
                )
        finally:
            _disconnect(conn)
    except Exception:
        await _recreate(admin_dsn)
        raise


def load_postgres(admin_dsn: str, ds: Dataset) -> None:
    asyncio.run(_load(admin_dsn, ds))


async def _fetch(admin_dsn: str, table: str, columns: tuple[str, ...]) -> list[tuple[Any, ...]]:
    conn = await asyncpg.connect(database_dsn(admin_dsn), timeout=5)
    try:
        cols = ", ".join(f'"{c}"' for c in columns)
        return [tuple(r) for r in await conn.fetch(f'SELECT {cols} FROM "{table}"')]
    finally:
        _disconnect(conn)


def fetch_all(admin_dsn: str, table: str, columns: tuple[str, ...]) -> list[tuple[Any, ...]]:
    return asyncio.run(_fetch(admin_dsn, table, columns))


async def _query(admin_dsn: str, sql: str) -> list[tuple[Any, ...]]:
    conn = await asyncpg.connect(database_dsn(admin_dsn), timeout=5)
    try:
        return [tuple(r) for r in await conn.fetch(sql)]
    finally:
        _disconnect(conn)


def query(admin_dsn: str, sql: str) -> list[tuple[Any, ...]]:
    return asyncio.run(_query(admin_dsn, sql))


async def _ping(admin_dsn: str) -> None:
    conn = await asyncpg.connect(admin_dsn, timeout=5)
    _disconnect(conn)


def ping(admin_dsn: str) -> None:
    asyncio.run(_ping(admin_dsn))
