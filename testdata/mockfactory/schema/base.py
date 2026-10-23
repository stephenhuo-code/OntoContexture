"""表定义的数据结构与建表语句生成（三种方言）。表与字段的中文说明只在这里写一处（research R9）。"""

from dataclasses import dataclass

DIALECTS = ("mysql", "postgres", "doris")

# 逻辑类型 → 各方言的列类型
_TYPES: dict[str, dict[str, str]] = {
    "code": {"mysql": "VARCHAR(32)", "postgres": "VARCHAR(32)", "doris": "VARCHAR(32)"},
    "name": {"mysql": "VARCHAR(100)", "postgres": "VARCHAR(100)", "doris": "VARCHAR(300)"},
    "text": {"mysql": "VARCHAR(500)", "postgres": "VARCHAR(500)", "doris": "VARCHAR(1500)"},
    "int": {"mysql": "INT", "postgres": "INTEGER", "doris": "INT"},
    "dec": {"mysql": "DECIMAL(10,4)", "postgres": "NUMERIC(10,4)", "doris": "DECIMAL(10,4)"},
    "rate": {"mysql": "DECIMAL(6,4)", "postgres": "NUMERIC(6,4)", "doris": "DECIMAL(6,4)"},
    "date": {"mysql": "DATE", "postgres": "DATE", "doris": "DATE"},
    "datetime": {"mysql": "DATETIME", "postgres": "TIMESTAMP", "doris": "DATETIME"},
}


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str


@dataclass(frozen=True)
class Table:
    system: str  # mes / qms / dw
    name: str
    comment: str
    columns: tuple[Column, ...]
    primary_key: tuple[str, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


def table(
    system: str, name: str, comment: str, pk: tuple[str, ...], *cols: tuple[str, str, str]
) -> Table:
    return Table(system, name, comment, tuple(Column(*c) for c in cols), pk)


def _quote(text: str) -> str:
    return text.replace("'", "''")


def ddl(t: Table, dialect: str) -> list[str]:
    if dialect not in DIALECTS:
        raise ValueError(f"不支持的方言：{dialect}")
    types = {c.name: _TYPES[c.type][dialect] for c in t.columns}
    if dialect == "mysql":
        cols = [
            f"`{c.name}` {types[c.name]}"
            + (" NOT NULL" if c.name in t.primary_key else "")
            + f" COMMENT '{_quote(c.comment)}'"
            for c in t.columns
        ]
        pk = ", ".join(f"`{k}`" for k in t.primary_key)
        body = ",\n  ".join([*cols, f"PRIMARY KEY ({pk})"])
        return [
            f"CREATE TABLE `{t.name}` (\n  {body}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 "
            f"COMMENT '{_quote(t.comment)}'"
        ]
    if dialect == "postgres":
        cols = [
            f'"{c.name}" {types[c.name]}' + (" NOT NULL" if c.name in t.primary_key else "")
            for c in t.columns
        ]
        pk = ", ".join(f'"{k}"' for k in t.primary_key)
        body = ",\n  ".join([*cols, f"PRIMARY KEY ({pk})"])
        stmts = [f'CREATE TABLE "{t.name}" (\n  {body}\n)']
        stmts.append(f"COMMENT ON TABLE \"{t.name}\" IS '{_quote(t.comment)}'")
        stmts += [
            f'COMMENT ON COLUMN "{t.name}"."{c.name}" IS \'{_quote(c.comment)}\'' for c in t.columns
        ]
        return stmts
    cols = [
        f"`{c.name}` {types[c.name]}"
        + (" NOT NULL" if c.name in t.primary_key else " NULL")
        + f" COMMENT '{_quote(c.comment)}'"
        for c in t.columns
    ]
    keys = ", ".join(f"`{k}`" for k in t.primary_key)
    body = ",\n  ".join(cols)
    return [
        f"CREATE TABLE `{t.name}` (\n  {body}\n) UNIQUE KEY({keys})\n"
        f"COMMENT '{_quote(t.comment)}'\n"
        f"DISTRIBUTED BY HASH(`{t.primary_key[0]}`) BUCKETS 1\n"
        f'PROPERTIES ("replication_num" = "1")'
    ]
