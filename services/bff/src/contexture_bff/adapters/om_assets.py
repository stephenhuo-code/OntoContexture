"""006 只读摘要与术语 / 标签详情：按身份读取 OpenMetadata 实体（research R9、R10；FR-012、FR-013）。

数据全部来自 OM 实体接口；实体不存在时返回 catalog.not_found，不补造（宪法 v2.2.0）。
"""

from typing import Any
from urllib.parse import quote

from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_search import governance
from contexture_bff.adapters.om_sources import split_fqn, split_tags
from contexture_core.auth import RequestContext
from contexture_core.errors import ContextureError

# dataAsset 各类型对应的 OM 实体接口（openmetadata-service/.../resources 的 @Path）
COLLECTIONS = {
    "table": "/tables",
    "storedProcedure": "/storedProcedures",
    "databaseSchema": "/databaseSchemas",
    "database": "/databases",
    "chart": "/charts",
    "dashboard": "/dashboards",
    "dashboardDataModel": "/dashboard/datamodels",
    "pipeline": "/pipelines",
    "topic": "/topics",
    "container": "/containers",
    "directory": "/drives/directories",
    "file": "/drives/files",
    "spreadsheet": "/drives/spreadsheets",
    "worksheet": "/drives/worksheets",
    "searchIndex": "/searchIndexes",
    "mlmodel": "/mlmodels",
    "dataProduct": "/dataProducts",
    "metric": "/metrics",
    "glossaryTerm": "/glossaryTerms",
    "tag": "/tags",
    "apiCollection": "/apiCollections",
    "apiEndpoint": "/apiEndpoints",
    "page": "/contextCenter/pages",
}
# research R9：各类型读取摘要时请求的 fields（"*" 为其他类型）
SUMMARY_FIELDS = {
    "table": "owners,domains,tags,dataProducts,columns,tableConstraints,certification",
    "database": "owners,domains,tags,dataProducts,certification",
    "databaseSchema": "owners,domains,tags,dataProducts,certification",
    "glossaryTerm": "owners,domains,tags,reviewers",
    "tag": "owners,domains,reviewers",
    "*": "owners,domains,tags",
}
GLOSSARY_TERM_FIELDS = "owners,reviewers,domains,tags,relatedTerms"
TAG_FIELDS = "owners,reviewers,domains"


def parent_table_fqn(column_fqn: str) -> str:
    """列 FQN 的前 4 段是所属表（服务.库.Schema.表），含点的名称以双引号包裹。"""
    return ".".join(split_fqn(column_fqn)[:4])


def _ref(r: Any) -> dict[str, Any] | None:
    if not isinstance(r, dict) or not r.get("id") or not r.get("type"):
        return None
    return {
        k: r[k]
        for k in ("id", "type", "name", "displayName", "fullyQualifiedName")
        if r.get(k) is not None
    }


def _refs(items: Any) -> list[dict[str, Any]]:
    return [x for x in (_ref(r) for r in items or []) if x]


def _breadcrumb(e: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for key, etype in (
        ("service", "databaseService"),
        ("database", "database"),
        ("databaseSchema", "databaseSchema"),
    ):
        ref = e.get(key)
        if isinstance(ref, dict):
            label = ref.get("displayName") or ref.get("name")
            if label:
                out.append({"entityType": etype, "label": str(label)})
    return out


def _columns(table: dict[str, Any]) -> list[dict[str, Any]]:
    """字段：名称、类型、主键或唯一约束（列级约束与表级约束合并）、描述、分类标签。"""
    by_table: dict[str, str] = {}
    for c in table.get("tableConstraints") or []:
        cols = list(c.get("columns") or [])
        if c.get("constraintType") in ("PRIMARY_KEY", "UNIQUE") and len(cols) == 1:
            by_table.setdefault(cols[0], str(c["constraintType"]))
    out = []
    for c in table.get("columns") or []:
        split = split_tags(c.get("tags"))
        tags = [t.get("tagFQN") for t in c.get("tags") or [] if t.get("tagFQN")]
        out.append(
            {
                "name": c["name"],
                "dataTypeDisplay": c.get("dataTypeDisplay") or c.get("dataType"),
                "constraint": c.get("constraint") or by_table.get(c["name"]),
                "description": c.get("description"),
                "displayName": c.get("displayName"),
                "tags": tags,
                "dataLevel": split.data_level,
            }
        )
    return out


def _not_found(fqn: str) -> ContextureError:
    return ContextureError("catalog.not_found", f"OpenMetadata 中不存在 {fqn}", status_code=404)


class AssetReader:
    def __init__(self, om: OmClient) -> None:
        self.om = om

    async def _get(self, path: str, ctx: RequestContext, fqn: str, fields: str) -> dict[str, Any]:
        raw = await self.om.request(
            ctx,
            "GET",
            f"{path}/name/{quote(fqn, safe='')}",
            params={"fields": fields},
            allow_404=True,
        )
        if not isinstance(raw, dict):
            raise _not_found(fqn)
        return raw

    async def summary(self, ctx: RequestContext, entity_type: str, fqn: str) -> dict[str, Any]:
        if entity_type == "tableColumn":
            table_fqn = parent_table_fqn(fqn)
            table = await self._get("/tables", ctx, table_fqn, SUMMARY_FIELDS["table"])
            name = split_fqn(fqn)[-1].strip('"')
            column = next((c for c in _columns(table) if c["name"] == name), None)
            if column is None:
                raise _not_found(fqn)
            return {
                "ref": {"entityType": "tableColumn", "id": fqn, "fqn": fqn},
                "name": name,
                "displayName": column.get("displayName"),
                "description": column.get("description"),
                "breadcrumb": [
                    *_breadcrumb(table),
                    {
                        "entityType": "table",
                        "label": str(table.get("displayName") or table["name"]),
                    },
                ],
                "governance": governance(table),
                "column": column,
                "parentTable": {
                    "entityType": "table",
                    "id": str(table.get("id") or ""),
                    "fqn": str(table.get("fullyQualifiedName") or table_fqn),
                },
            }
        path = COLLECTIONS.get(entity_type)
        if path is None:
            raise ContextureError(
                "search.invalid_criteria",
                f"不支持的资产类型：{entity_type}",
                status_code=422,
                details={"field": "entityType"},
            )
        e = await self._get(path, ctx, fqn, SUMMARY_FIELDS.get(entity_type, SUMMARY_FIELDS["*"]))
        out: dict[str, Any] = {
            "ref": {
                "entityType": entity_type,
                "id": str(e.get("id") or ""),
                "fqn": str(e.get("fullyQualifiedName") or fqn),
            },
            "name": str(e.get("name") or ""),
            "displayName": e.get("displayName"),
            "description": e.get("description"),
            "breadcrumb": _breadcrumb(e),
            "governance": governance(e),
        }
        if entity_type == "table":
            out["columns"] = _columns(e)
        return out

    async def glossary_term(self, ctx: RequestContext, fqn: str) -> dict[str, Any]:
        e = await self._get("/glossaryTerms", ctx, fqn, GLOSSARY_TERM_FIELDS)
        return {
            "ref": {
                "entityType": "glossaryTerm",
                "id": str(e.get("id") or ""),
                "fqn": str(e.get("fullyQualifiedName") or fqn),
            },
            "name": str(e.get("name") or ""),
            "displayName": e.get("displayName"),
            "description": e.get("description"),
            "glossary": _ref(e.get("glossary")),
            "parent": _ref(e.get("parent")),
            "synonyms": [str(s) for s in e.get("synonyms") or []],
            "relatedTerms": _refs(e.get("relatedTerms")),
            "references": [
                {"name": str(r.get("name") or ""), "endpoint": str(r.get("endpoint") or "")}
                for r in e.get("references") or []
                if isinstance(r, dict)
            ],
            "owners": _refs(e.get("owners")),
            "reviewers": _refs(e.get("reviewers")),
            "domains": _refs(e.get("domains")),
            "tags": [t["tagFQN"] for t in e.get("tags") or [] if t.get("tagFQN")],
            "entityStatus": e.get("entityStatus"),
            "origin": split_tags(e.get("tags")).origin,
        }

    async def tag(self, ctx: RequestContext, fqn: str) -> dict[str, Any]:
        e = await self._get("/tags", ctx, fqn, TAG_FIELDS)
        return {
            "ref": {
                "entityType": "tag",
                "id": str(e.get("id") or ""),
                "fqn": str(e.get("fullyQualifiedName") or fqn),
            },
            "name": str(e.get("name") or ""),
            "displayName": e.get("displayName"),
            "description": e.get("description"),
            "classification": _ref(e.get("classification")),
            "parent": _ref(e.get("parent")),
            "owners": _refs(e.get("owners")),
            "reviewers": _refs(e.get("reviewers")),
            "domains": _refs(e.get("domains")),
            "deprecated": bool(e.get("deprecated", False)),
        }
