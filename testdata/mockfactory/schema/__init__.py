"""三套模拟系统的表定义（单一来源）：由它生成建表语句与数据说明。"""

from mockfactory.schema import dw, mes, qms
from mockfactory.schema.base import DIALECTS, Column, Table, ddl

SYSTEMS = ("mes", "qms", "dw")
TABLES: list[Table] = [*mes.TABLES, *qms.TABLES, *dw.TABLES]
DIALECT_OF = {"mes": "mysql", "qms": "postgres", "dw": "doris"}


def tables_of(system: str) -> list[Table]:
    return [t for t in TABLES if t.system == system]


__all__ = [
    "DIALECTS",
    "DIALECT_OF",
    "SYSTEMS",
    "TABLES",
    "Column",
    "Table",
    "ddl",
    "tables_of",
]
