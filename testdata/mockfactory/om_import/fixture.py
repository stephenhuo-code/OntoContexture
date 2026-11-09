"""开发态测试元数据的 fixture：由 003 表定义（mockfactory.schema）生成 OM 的 PUT 请求体。

规则见 specs/006-asset-search-summary/research.md R12、R13 与 data-model.md 第 6 节：
- 服务不带连接，描述注明是开发态测试元数据；
- 工具创建的每个实体都贴开发态标识标签（MARKER_FQN）；
  分类本身没有 tags 字段，用描述前缀 OWNED_SENTINEL 识别；
- 样例覆盖同名表、缺负责人、缺分级、缺业务域、业务域 × 分级 × 标签组合、
  带数据级别标签的字段、无显示名。
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from mockfactory.schema import DIALECT_OF, TABLES, Table
from mockfactory.schema.base import dialect_type

SERVICE_PREFIX = "devtest-"
OWNED_SENTINEL = "[织境开发态测试元数据]"
SERVICE_NOTE = "开发态测试元数据，由 testdata 导入工具生成"

MARKER_CLASSIFICATION = "ContextureDevTest"
MARKER_TAG = "DevTestMetadata"
MARKER_FQN = f"{MARKER_CLASSIFICATION}.{MARKER_TAG}"
SAMPLE_CLASSIFICATION = "ContextureDevSample"
SAMPLE_TAGS = {"mes": "生产相关", "qms": "质量相关"}
GLOSSARY = "ContextureDevGlossary"
DOMAINS = {"mes": "DevTestProduction", "qms": "DevTestQuality"}
DOMAIN_LABELS = {"DevTestProduction": "开发态-生产域", "DevTestQuality": "开发态-质量域"}
DATA_LEVEL = "数据级别"  # 由 make seed 创建（tools/seed.py），本工具只引用，不创建

# 系统 → (服务名, OM serviceType, 库名, Schema 名)
SYSTEMS = {
    "mes": (f"{SERVICE_PREFIX}mes", "Mysql", "default", "mes"),
    "qms": (f"{SERVICE_PREFIX}qms", "Postgres", "qms", "public"),
    "dw": (f"{SERVICE_PREFIX}dw", "Doris", "default", "mock_dw"),
}
# 同名表样例：在另一个 Schema 下再放一张同名表
DUPLICATE = ("mes", "mes_archive", "work_order")
# 无显示名样例
NO_DISPLAY_NAME = "supplier"
# 业务术语样例：(术语名, 描述, 关联的表)
TERMS = (
    ("工单", "开发态样例术语：生产工单。", "work_order"),
    ("检验记录", "开发态样例术语：质量检验记录。", "inspection_record"),
    ("不合格品", "开发态样例术语：不合格品报告（NCR）。", "ncr"),
)
TEAM_NAMES = ("admin", "ai-engineer")

COLLECTION = {
    "classification": "classifications",
    "tag": "tags",
    "domain": "domains",
    "glossary": "glossaries",
    "glossaryTerm": "glossaryTerms",
    "databaseService": "services/databaseServices",
    "database": "databases",
    "databaseSchema": "databaseSchemas",
    "table": "tables",
}
_PARENT = {
    "tags": "classification",
    "glossaryTerms": "glossary",
    "databases": "service",
    "databaseSchemas": "database",
    "tables": "databaseSchema",
}


@dataclass(frozen=True)
class Entity:
    kind: str
    fqn: str
    body: dict[str, Any] = field(hash=False)
    system: str | None = None

    @property
    def collection(self) -> str:
        return COLLECTION[self.kind]


def fqn_of(collection: str, body: Mapping[str, Any]) -> str:
    parent = _PARENT.get(collection)
    return f"{body[parent]}.{body['name']}" if parent else str(body["name"])


def _label(fqn: str, source: str = "Classification") -> dict[str, str]:
    return {"tagFQN": fqn, "source": source, "labelType": "Manual", "state": "Confirmed"}


MARKER = _label(MARKER_FQN)


def _entity(kind: str, body: dict[str, Any], system: str | None = None) -> Entity:
    return Entity(kind, fqn_of(COLLECTION[kind], body), body, system)


def _column(table: Table, index: int) -> dict[str, Any]:
    col = table.columns[index]
    display = dialect_type(col.type, DIALECT_OF[table.system])
    base, _, args = display.partition("(")
    data_type = {"VARCHAR": "VARCHAR", "INT": "INT", "INTEGER": "INT", "NUMERIC": "DECIMAL"}.get(
        base, base
    )
    out: dict[str, Any] = {
        "name": col.name,
        "dataType": data_type,
        "dataTypeDisplay": display.lower(),
        "description": col.comment,
    }
    numbers = [int(n) for n in re.findall(r"\d+", args)]
    if data_type == "VARCHAR":
        out["dataLength"] = numbers[0]
    elif data_type == "DECIMAL" and numbers:
        out["precision"], out["scale"] = numbers[0], numbers[1]
    level = _data_level(table, col.name)
    if level:
        out["tags"] = [_label(f"{DATA_LEVEL}.{level}")]
    return out


def _data_level(table: Table, column: str) -> str | None:
    if column == table.primary_key[0]:
        return "一级"
    if table.name == "employee":
        return "三级"
    if table.name == "customer":
        return "二级"
    return None


def _table(
    table: Table, index: int, schema_fqn: str, owners: Mapping[str, dict[str, Any]]
) -> Entity:
    tags = [MARKER]
    tier = ("Tier.Tier1", "Tier.Tier2", None)[index % 3]
    if tier:
        tags.append(_label(tier))
    if table.system in SAMPLE_TAGS:
        tags.append(_label(f"{SAMPLE_CLASSIFICATION}.{SAMPLE_TAGS[table.system]}"))
    tags += [_label(f"{GLOSSARY}.{t}", "Glossary") for t, _, name in TERMS if name == table.name]
    body: dict[str, Any] = {
        "name": table.name,
        "databaseSchema": schema_fqn,
        "description": table.comment,
        "tableType": "Regular",
        "columns": [_column(table, i) for i in range(len(table.columns))],
        "tableConstraints": [{"constraintType": "PRIMARY_KEY", "columns": list(table.primary_key)}],
        "tags": tags,
    }
    if table.name != NO_DISPLAY_NAME:
        body["displayName"] = table.comment
    if index % 4 != 3:
        body["owners"] = [owners[TEAM_NAMES[index % 2]]]
    if table.system in DOMAINS:
        body["domains"] = [DOMAINS[table.system]]
    return _entity("table", body, table.system)


def build(owners: Mapping[str, dict[str, Any]]) -> list[Entity]:
    """按写入顺序返回全部实体：分类 → 标签 → 业务域 → 术语表 → 术语 → 服务 → 库 → Schema → 表。"""
    out = [
        _entity(
            "classification",
            {
                "name": MARKER_CLASSIFICATION,
                "displayName": "开发态测试标识",
                "description": f"{OWNED_SENTINEL} 标识由 testdata 导入工具生成的开发态测试元数据。",
            },
        ),
        _entity(
            "classification",
            {
                "name": SAMPLE_CLASSIFICATION,
                "displayName": "开发态样例标签",
                "description": f"{OWNED_SENTINEL} 开发态样例分类标签，用于组合筛选验收。",
            },
        ),
        _entity(
            "tag",
            {
                "classification": MARKER_CLASSIFICATION,
                "name": MARKER_TAG,
                "displayName": "开发态测试元数据",
                "description": f"{OWNED_SENTINEL} 带此标签的资产来自开发态导入，不是已连通的源库。",
            },
        ),
    ]
    out += [
        _entity(
            "tag",
            {
                "classification": SAMPLE_CLASSIFICATION,
                "name": name,
                "description": f"{OWNED_SENTINEL} 开发态样例标签。",
            },
        )
        for name in SAMPLE_TAGS.values()
    ]
    out += [
        _entity(
            "domain",
            {
                "name": name,
                "displayName": DOMAIN_LABELS[name],
                "description": f"{OWNED_SENTINEL} 开发态样例业务域。",
                "domainType": "Aggregate",
                "tags": [MARKER],
            },
        )
        for name in DOMAINS.values()
    ]
    out.append(
        _entity(
            "glossary",
            {
                "name": GLOSSARY,
                "displayName": "开发态测试术语表",
                "description": f"{OWNED_SENTINEL} 开发态样例业务术语。",
                "tags": [MARKER],
            },
        )
    )
    out += [
        _entity(
            "glossaryTerm",
            {"glossary": GLOSSARY, "name": name, "description": desc, "tags": [MARKER]},
        )
        for name, desc, _ in TERMS
    ]
    for system, (service, service_type, _db, _schema) in SYSTEMS.items():
        out.append(
            _entity(
                "databaseService",
                {
                    "name": service,
                    "serviceType": service_type,
                    "description": f"{SERVICE_NOTE}（003 {system.upper()} 表定义），未配置连接。",
                    "tags": [MARKER],
                },
                system,
            )
        )
    databases = {(s[0], s[2]) for s in SYSTEMS.values()}
    out += [
        _entity("database", {"name": db, "service": svc, "tags": [MARKER]})
        for svc, db in sorted(databases)
    ]
    schemas = [(f"{svc}.{db}", schema) for svc, _, db, schema in SYSTEMS.values()]
    dup_system, dup_schema, _ = DUPLICATE
    schemas.append((f"{SYSTEMS[dup_system][0]}.{SYSTEMS[dup_system][2]}", dup_schema))
    out += [
        _entity("databaseSchema", {"name": schema, "database": db_fqn, "tags": [MARKER]})
        for db_fqn, schema in schemas
    ]
    for index, table in enumerate(TABLES):
        svc, _, db, schema = SYSTEMS[table.system]
        out.append(_table(table, index, f"{svc}.{db}.{schema}", owners))
    dup = next(t for t in TABLES if t.system == dup_system and t.name == DUPLICATE[2])
    svc, _, db, _ = SYSTEMS[dup_system]
    out.append(_table(dup, TABLES.index(dup) + 1, f"{svc}.{db}.{dup_schema}", owners))
    return out


def is_owned(kind: str, body: Mapping[str, Any]) -> bool:
    """判断 OM 中已有的实体是否由本工具创建。"""
    if kind == "classification":
        return str(body.get("description", "")).startswith(OWNED_SENTINEL)
    return any(t.get("tagFQN") == MARKER_FQN for t in body.get("tags") or [])
