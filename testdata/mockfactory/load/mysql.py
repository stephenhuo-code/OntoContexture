"""写入模拟 MES（MySQL）：重建 database `mes`、建表、多行 INSERT；失败时清空。"""

from typing import Any

import pymysql

from mockfactory.dataset import Dataset
from mockfactory.schema import ddl, tables_of

DATABASE = "mes"
BATCH_SIZE = 2000


def connect(target: dict[str, Any], database: str | None = None) -> "pymysql.Connection[Any]":
    return pymysql.connect(
        **target, database=database, charset="utf8mb4", autocommit=True, connect_timeout=5
    )


def _recreate(cur: Any) -> None:
    cur.execute(f"DROP DATABASE IF EXISTS `{DATABASE}`")
    cur.execute(f"CREATE DATABASE `{DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")


def load_mysql(target: dict[str, Any], ds: Dataset) -> None:
    conn = connect(target)
    try:
        with conn.cursor() as cur:
            _recreate(cur)
            cur.execute(f"USE `{DATABASE}`")
            try:
                for t in tables_of(DATABASE):
                    for stmt in ddl(t, "mysql"):
                        cur.execute(stmt)
                    cols = ", ".join(f"`{c}`" for c in t.column_names)
                    marks = ", ".join(["%s"] * len(t.columns))
                    sql = f"INSERT INTO `{t.name}` ({cols}) VALUES ({marks})"
                    rows = ds.rows[t.name]
                    for i in range(0, len(rows), BATCH_SIZE):
                        cur.executemany(sql, rows[i : i + BATCH_SIZE])
            except Exception:
                _recreate(cur)
                raise
    finally:
        conn.close()


def fetch_all(
    target: dict[str, Any], table: str, columns: tuple[str, ...]
) -> list[tuple[Any, ...]]:
    conn = connect(target, DATABASE)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {', '.join(f'`{c}`' for c in columns)} FROM `{table}`")
            return list(cur.fetchall())
    finally:
        conn.close()
