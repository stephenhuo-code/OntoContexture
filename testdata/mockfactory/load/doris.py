"""写入模拟数仓（Doris 的 database `mock_dw`，经 MySQL 协议）：重建、建表、批量 INSERT、
只读账号；失败时删除。

Stream Load 需要从本机直连 BE，经端口转发不可达，因此用 INSERT（research R6）。
"""

from typing import Any, Protocol

from mockfactory.dataset import Dataset
from mockfactory.schema import ddl, tables_of

DATABASE = "mock_dw"
# 本地 Doris BE 内存上限约 3.2 GB、空闲已占 2 GB 以上，每批 5000 行会触发 MEM_LIMIT_EXCEEDED
BATCH_SIZE = 1000
READER = "mock_dw_reader"


class Connection(Protocol):
    def cursor(self) -> Any: ...


def _literal(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"


def load_doris(conn: Connection, ds: Dataset, reader_password: str | None) -> None:
    drop = f"DROP DATABASE IF EXISTS `{DATABASE}` FORCE"
    with conn.cursor() as cur:
        cur.execute(drop)
        cur.execute(f"CREATE DATABASE `{DATABASE}`")
        try:
            for t in tables_of("dw"):
                for stmt in ddl(t, "doris"):
                    cur.execute(stmt.replace("CREATE TABLE `", f"CREATE TABLE `{DATABASE}`.`", 1))
                cols = ", ".join(f"`{c}`" for c in t.column_names)
                marks = ", ".join(["%s"] * len(t.columns))
                sql = f"INSERT INTO `{DATABASE}`.`{t.name}` ({cols}) VALUES ({marks})"
                rows = ds.rows[t.name]
                for i in range(0, len(rows), BATCH_SIZE):
                    cur.executemany(sql, rows[i : i + BATCH_SIZE])
        except Exception:
            cur.execute(drop)
            raise
        if reader_password:
            user = f"'{READER}'@'%'"
            cur.execute(
                f"CREATE USER IF NOT EXISTS {user} IDENTIFIED BY {_literal(reader_password)}"
            )
            cur.execute(f"SET PASSWORD FOR {user} = PASSWORD({_literal(reader_password)})")
            cur.execute(f"GRANT SELECT_PRIV ON internal.{DATABASE}.* TO {user}")


def fetch_all(conn: Connection, table: str, columns: tuple[str, ...]) -> list[tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(f'`{c}`' for c in columns)} FROM `{DATABASE}`.`{table}`")
        return list(cur.fetchall())
