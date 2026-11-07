"""005 测试数据：只读元数据账号与 viewlab 视图测试库（spec Clarification 2026-11-07，research R10）。

- 只读账号：`mes_meta_ro`（mock-mes 的 MySQL，库 mes）、`qms_meta_ro`（mock-qms 的 PostgreSQL，库 qms），
  供织境以 OpenMetadata 原生采集读取元数据；不改动 003 的表与数据。
- viewlab：在同一两个实例内各建独立数据库 `viewlab`（基表 + 引用基表的视图），以及
  `viewlab_ro`（可读视图定义）与 `viewlab_noview`（MySQL 不授予 SHOW VIEW，读不到视图定义）。
- LINEAGE 是视图血缘的标准答案：视图 → 上游表与字段级映射，用于核对 OM 写入的血缘（SC-005）。

全部为合成数据，不进入客户交付物；重复执行幂等（存在即跳过或重置密码）。
"""

import asyncio
import base64
import subprocess
from datetime import date
from typing import Any
from urllib.parse import urlparse

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import pymysql

DATABASE = "viewlab"
ACCOUNTS = ("mes_meta_ro", "qms_meta_ro", "viewlab_ro", "viewlab_noview")
SECRET = "mock-readonly"  # 命名空间 mock-sources；键与 ACCOUNTS 相同（下划线换为连字符）

TABLES = {
    "supplier": [
        ("supplier_code", "VARCHAR(16)", "供应商编码", True),
        ("supplier_name", "VARCHAR(64)", "供应商名称", False),
        ("region", "VARCHAR(32)", "所在地区", False),
    ],
    "purchase_order": [
        ("order_no", "VARCHAR(20)", "采购订单号", True),
        ("supplier_code", "VARCHAR(16)", "供应商编码", False),
        ("material_code", "VARCHAR(20)", "物料编码", False),
        ("quantity", "INTEGER", "订购数量", False),
        ("order_date", "DATE", "下单日期", False),
    ],
}
ROWS = {
    "supplier": [("S001", "华东精密件", "江苏"), ("S002", "北方铸造", "河北")],
    "purchase_order": [
        ("PO260901", "S001", "M-1001", 120, date(2026, 9, 1)),
        ("PO260902", "S002", "M-2002", 80, date(2026, 9, 2)),
        ("PO260903", "S001", "M-1002", 45, date(2026, 9, 3)),
    ],
}
VIEWS = {
    "v_supplier_orders": (
        "SELECT o.order_no, o.material_code, o.quantity, s.supplier_name "
        "FROM purchase_order o JOIN supplier s ON o.supplier_code = s.supplier_code"
    ),
    "v_order_qty_by_supplier": (
        "SELECT supplier_code, SUM(quantity) AS total_quantity "
        "FROM purchase_order GROUP BY supplier_code"
    ),
}
# 标准答案：视图 → 上游表，以及视图字段 ← 上游 表.字段
LINEAGE: dict[str, dict[str, Any]] = {
    "v_supplier_orders": {
        "tables": ["purchase_order", "supplier"],
        "columns": {
            "order_no": ["purchase_order.order_no"],
            "material_code": ["purchase_order.material_code"],
            "quantity": ["purchase_order.quantity"],
            "supplier_name": ["supplier.supplier_name"],
        },
    },
    "v_order_qty_by_supplier": {
        "tables": ["purchase_order"],
        "columns": {
            "supplier_code": ["purchase_order.supplier_code"],
            "total_quantity": ["purchase_order.quantity"],
        },
    },
}


def _create_table(name: str, dialect: str) -> list[str]:
    cols = TABLES[name]
    pk = [c[0] for c in cols if c[3]]
    if dialect == "mysql":
        body = ", ".join(f"`{c}` {t} COMMENT '{d}'" for c, t, d, _ in cols)
        return [
            f"CREATE TABLE IF NOT EXISTS `{name}` ({body}, PRIMARY KEY (`{'`, `'.join(pk)}`))"
            f" COMMENT='viewlab：{name}'"
        ]
    body = ", ".join(f'"{c}" {t}' for c, t, _, _ in cols)
    keys = ", ".join(f'"{c}"' for c in pk)
    stmts = [f'CREATE TABLE IF NOT EXISTS "{name}" ({body}, PRIMARY KEY ({keys}))']
    stmts += [f"""COMMENT ON COLUMN "{name}"."{c}" IS '{d}'""" for c, _, d, _ in cols]
    return stmts


# ---------- MySQL（mock-mes 实例） ----------


def provision_mysql(admin: dict[str, Any], passwords: dict[str, str]) -> None:
    conn = pymysql.connect(**admin, charset="utf8mb4", autocommit=True, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DATABASE}` CHARACTER SET utf8mb4")
            cur.execute(f"USE `{DATABASE}`")
            for table in TABLES:
                for stmt in _create_table(table, "mysql"):
                    cur.execute(stmt)
                cols = ", ".join(f"`{c[0]}`" for c in TABLES[table])
                marks = ", ".join(["%s"] * len(TABLES[table]))
                cur.executemany(f"INSERT IGNORE INTO `{table}` ({cols}) VALUES ({marks})", ROWS[table])
            for view, sql in VIEWS.items():
                cur.execute(f"CREATE OR REPLACE VIEW `{view}` AS {sql}")
            grants = {
                "mes_meta_ro": ["GRANT SELECT, SHOW VIEW ON `mes`.* TO 'mes_meta_ro'@'%'"],
                "viewlab_ro": [f"GRANT SELECT, SHOW VIEW ON `{DATABASE}`.* TO 'viewlab_ro'@'%'"],
                # 受限账号：只授 SELECT，不授 SHOW VIEW → information_schema.VIEWS 中视图定义为空
                "viewlab_noview": [f"GRANT SELECT ON `{DATABASE}`.* TO 'viewlab_noview'@'%'"],
            }
            for user, stmts in grants.items():
                # 带参数执行时主机通配符须写作 %%
                cur.execute(f"CREATE USER IF NOT EXISTS '{user}'@'%%' IDENTIFIED BY %s", (passwords[user],))
                cur.execute(f"ALTER USER '{user}'@'%%' IDENTIFIED BY %s", (passwords[user],))
                for stmt in stmts:
                    cur.execute(stmt)
    finally:
        conn.close()


# ---------- PostgreSQL（mock-qms 实例） ----------


def _dsn(admin_dsn: str, database: str) -> str:
    return urlparse(admin_dsn)._replace(path=f"/{database}").geturl()


async def _provision_postgres(admin_dsn: str, passwords: dict[str, str]) -> None:
    admin = await asyncpg.connect(admin_dsn, timeout=10)
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", DATABASE):
            await admin.execute(f'CREATE DATABASE "{DATABASE}"')
        for user in ("qms_meta_ro", "viewlab_ro", "viewlab_noview"):
            password = passwords[user].replace("'", "''")
            if await admin.fetchval("SELECT 1 FROM pg_roles WHERE rolname=$1", user):
                await admin.execute(f"ALTER ROLE \"{user}\" WITH LOGIN PASSWORD '{password}'")
            else:
                await admin.execute(f"CREATE ROLE \"{user}\" WITH LOGIN PASSWORD '{password}'")
    finally:
        admin.terminate()

    lab = await asyncpg.connect(_dsn(admin_dsn, DATABASE), timeout=10)
    try:
        for table in TABLES:
            for stmt in _create_table(table, "postgres"):
                await lab.execute(stmt)
            cols = ", ".join(f'"{c[0]}"' for c in TABLES[table])
            marks = ", ".join(f"${i + 1}" for i in range(len(TABLES[table])))
            await lab.executemany(
                f'INSERT INTO "{table}" ({cols}) VALUES ({marks}) ON CONFLICT DO NOTHING', ROWS[table]
            )
        for view, sql in VIEWS.items():
            await lab.execute(f'CREATE OR REPLACE VIEW "{view}" AS {sql}')
        # PostgreSQL 的 pg_get_viewdef 对所有可连接角色可读，无法用权限复现“视图定义不可读”（research R10）；
        # viewlab_noview 在 PostgreSQL 上与 viewlab_ro 同权，仅为保持账号集合一致
        for user in ("viewlab_ro", "viewlab_noview"):
            await lab.execute(f'GRANT CONNECT ON DATABASE "{DATABASE}" TO "{user}"')
            await lab.execute(f'GRANT USAGE ON SCHEMA public TO "{user}"')
            await lab.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{user}"')
    finally:
        lab.terminate()

    qms = await asyncpg.connect(_dsn(admin_dsn, "qms"), timeout=10)
    try:
        await qms.execute('GRANT CONNECT ON DATABASE "qms" TO "qms_meta_ro"')
        await qms.execute('GRANT USAGE ON SCHEMA public TO "qms_meta_ro"')
        await qms.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO "qms_meta_ro"')
    finally:
        qms.terminate()


def provision_postgres(admin_dsn: str, passwords: dict[str, str]) -> None:
    asyncio.run(_provision_postgres(admin_dsn, passwords))


# ---------- 本地集群 ----------


def local_passwords(context: str = "kind-contexture") -> dict[str, str]:
    """读取 mock-sources/mock-readonly（testdata/deploy/secrets.sh 生成）。"""
    out: dict[str, str] = {}
    for user in ACCOUNTS:
        key = user.replace("_", "-")
        raw = subprocess.run(  # noqa: S603
            ["kubectl", "--context", context, "-n", "mock-sources", "get", "secret", SECRET,  # noqa: S607
             "-o", f"jsonpath={{.data.{key}}}"],
            check=True, capture_output=True, text=True,
        ).stdout
        out[user] = base64.b64decode(raw).decode()
    return out
