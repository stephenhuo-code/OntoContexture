"""006 资产搜索：调用 OpenMetadata 2.0.3 的搜索接口（research R1–R8、R11）。

BFF 只做结构化条件 → OM 参数的翻译、校验与结果投影；不自建索引，不打分（FR-018、FR-019）。
浏览器只提交 SearchCriteria，不提交任何查询语句；OM 解析 query_filter 失败时会静默忽略，
所以 DSL 一律由本模块构造，并由单元测试保证结构。
"""

import asyncio
import html
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_sources import split_tags
from contexture_core.auth import RequestContext
from contexture_core.errors import ContextureError, UpstreamUnavailable

# OM 索引缺失：OpenSearch 404 → SearchIndexNotFoundException → HTTP 500「Failed to find index …」
# （OpenSearchSearchManager.java:1231-1237）
INDEX_MISSING_PREFIX = "Failed to find index"

# dataAsset 别名覆盖的 24 类实体（indexMapping.json，parentAliases 含 dataAsset；别名与类型同名）
ENTITY_TYPES: tuple[str, ...] = (
    "table",
    "tableColumn",
    "storedProcedure",
    "databaseSchema",
    "database",
    "chart",
    "dashboard",
    "dashboardDataModel",
    "pipeline",
    "topic",
    "container",
    "directory",
    "file",
    "spreadsheet",
    "worksheet",
    "searchIndex",
    "mlmodel",
    "dataProduct",
    "metric",
    "glossaryTerm",
    "tag",
    "apiCollection",
    "apiEndpoint",
    "page",
)
# 排序（$UI/constants/explore.constants.ts:19,40-106）
SORT_FIELDS = {
    "popularity": "totalVotes",
    "name": "displayName.keyword",
    "relevance": "_score",
    "updatedAt": "updatedAt",
}
SORT_ORDERS = ("asc", "desc")
PAGE_SIZES = (15, 25, 50)
RESULT_WINDOW = 10000  # searchSettings.maxResultHits
MAX_KEYWORD = 200
MAX_VALUES = 50
MAX_OPTION_QUERY = 100
_RESERVED = set('+-=&|><!(){}[]^"~*?:\\/')
_OPERATOR = re.compile(r"\b(AND|OR|NOT)\b")
_HIGHLIGHT = re.compile(r'<span class="text-highlighter">(.*?)</span>', re.S)
# 命中字段统计时忽略的键（$UI/components/SearchedData/SearchedData.tsx:55-60）
_SKIP_HIGHLIGHT_KEYS = {"table_name", "topic_name", "dashboard_name", "pipeline_name"}
SUGGESTION_SIZE = 15
SUGGESTIONS_PER_TYPE = 5
SUGGESTION_FIELDS = [
    "id",
    "name",
    "displayName",
    "fullyQualifiedName",
    "entityType",
    "serviceType",
    "service.displayName",
    "table",
]

# 快速筛选维度 → (OM 字段, 显示名来源字段)；research R4
# （$UI/constants/AdvancedSearch.constants.ts:69-139）
FACETS: dict[str, tuple[str, str | None]] = {
    "entityType": ("entityType", None),
    "domain": ("domains.displayName.keyword", "domains.displayName"),
    "dataProduct": ("dataProducts.displayName.keyword", "dataProducts.displayName"),
    "owner": ("ownerDisplayName", None),
    "tag": ("tags.tagFQN", None),
    "tier": ("tier.tagFQN", None),
    "service": ("service.displayName.keyword", "service.displayName"),
    "serviceType": ("serviceType", "serviceType"),
    "certification": ("certification.tagLabel.tagFQN", None),
    "database": ("database.displayName.keyword", "database.displayName"),
    "databaseSchema": ("databaseSchema.displayName.keyword", "databaseSchema.displayName"),
    "column": ("columns.name.keyword", None),
    "tableType": ("tableType", None),
    "columnDescriptionStatus": ("columnDescriptionStatus", None),
}
TABLE_ONLY = {"database", "databaseSchema", "column", "tableType", "columnDescriptionStatus"}
# 支持「无」的维度（spec FR-008）
NONE_DIMENSIONS = {"owner", "domain", "tier", "tag", "certification"}

# 浏览树（research R3；$UI/utils/SearchClassBase.ts:236-420）：大类 → (显示名, 子实体类型, 层级)
# 显示名取 OM 中文界面（locale/languages/zh-cn.json），治理与业务域沿用 005 的叫法
_DB_LEVELS = ("serviceType", "service", "database", "databaseSchema", "entityType")
_SERVICE_LEVELS = ("serviceType", "service", "entityType")
BROWSE_ROOTS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "databases": (
        "数据库",
        ("database", "databaseSchema", "storedProcedure", "table", "tableColumn"),
        _DB_LEVELS,
    ),
    "dashboards": ("仪表板", ("dashboardDataModel", "dashboard", "chart"), _SERVICE_LEVELS),
    "pipelines": ("工作流", ("pipeline",), _SERVICE_LEVELS),
    "topics": ("消息主题", ("topic",), _SERVICE_LEVELS),
    "mlmodels": ("机器学习模型", ("mlmodel",), _SERVICE_LEVELS),
    "containers": ("存储容器", ("container",), _SERVICE_LEVELS),
    "searchIndexes": ("搜索索引", ("searchIndex",), _SERVICE_LEVELS),
    "apis": ("APIs", ("apiEndpoint", "apiCollection"), _SERVICE_LEVELS),
    "drives": ("驱动器", ("directory", "file", "spreadsheet", "worksheet"), _SERVICE_LEVELS),
    "governance": ("数据治理", ("tag", "glossaryTerm", "metric"), ("entityType",)),
    "domains": ("业务域", ("dataProduct",), ("entityType",)),
}
# 浏览树各层使用的字段：用原始大小写的 keyword 字段，桶键即可作为显示名（serviceType 只有小写字段）
BROWSE_FIELDS = {
    "serviceType": ("serviceType", "serviceType"),
    "service": ("service.displayName", None),
    "database": ("database.displayName", None),
    "databaseSchema": ("databaseSchema.displayName", None),
    "entityType": ("entityType", None),
}
BROWSE_BUCKETS = 1000
FACET_SIZE = 10  # /search/aggregate 默认 size（SearchResource.java:746-812）
_REGEX_RESERVED = set('.?+*|{}[]()"\\#@&<>~')


def invalid(field: str, reason: str) -> ContextureError:
    return ContextureError(
        "search.invalid_criteria", reason, status_code=422, details={"field": field}
    )


@dataclass(frozen=True)
class Criteria:
    keyword: str = ""
    scope: str | None = None
    entity_type: str | None = None
    browse_path: tuple[tuple[str, str], ...] = ()
    filters: Mapping[str, tuple[tuple[str, ...], bool]] = field(default_factory=dict)
    sort_field: str = "popularity"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 15


def _entity(raw: Any, name: str) -> str | None:
    if raw is None:
        return None
    if raw not in ENTITY_TYPES:
        raise invalid(name, f"不支持的资产类型：{raw}")
    return str(raw)


_NEXT_LEVEL = {
    "root": ("serviceType", "entityType"),
    "serviceType": ("service",),
    "service": ("database", "entityType"),
    "database": ("databaseSchema",),
    "databaseSchema": ("entityType",),
    "entityType": (),
}


def parse_browse_path(
    raw: Any, name: str = "browsePath", limit: int = 6
) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) > limit:
        raise invalid(name, f"位置条件最多 {limit} 层")
    steps: list[tuple[str, str]] = []
    for i, step in enumerate(raw):
        if not isinstance(step, dict):
            raise invalid(name, "位置条件格式不正确")
        level, value = step.get("level"), step.get("value")
        if not isinstance(value, str) or not value or len(value) > 256:
            raise invalid(name, "位置条件的取值不能为空")
        if i == 0:
            if level != "root" or value not in BROWSE_ROOTS:
                raise invalid(name, "位置条件的第一层必须是资产大类")
        else:
            prev = steps[-1][0]
            if level not in _NEXT_LEVEL[prev]:
                raise invalid(name, f"位置条件不能从 {prev} 跳到 {level}")
            root_levels = BROWSE_ROOTS[steps[0][1]][2]
            if i - 1 >= len(root_levels) or root_levels[i - 1] != level:
                raise invalid(name, f"{steps[0][1]} 大类下第 {i} 层不是 {level}")
        steps.append((str(level), value))
    return tuple(steps)


def parse_criteria(raw: Mapping[str, Any]) -> Criteria:
    """按 data-model 第 2 节校验；不合法时返回 search.invalid_criteria，不静默忽略（FR-019）。"""
    keyword = raw.get("keyword") or ""
    if not isinstance(keyword, str):
        raise invalid("keyword", "关键词必须是文本")
    keyword = keyword.strip()
    if len(keyword) > MAX_KEYWORD:
        raise invalid("keyword", f"关键词最多 {MAX_KEYWORD} 个字符")
    scope = _entity(raw.get("scope"), "scope")
    entity_type = _entity(raw.get("entityType"), "entityType")
    if scope and entity_type and scope != entity_type:
        raise invalid("entityType", "资产类型与搜索范围不一致")
    filters: dict[str, tuple[tuple[str, ...], bool]] = {}
    for dim, value in (raw.get("filters") or {}).items():
        if dim not in FACETS:
            raise invalid("filters", f"不支持的筛选维度：{dim}")
        if dim in TABLE_ONLY and (entity_type or scope) != "table":
            raise invalid("filters", f"筛选维度 {dim} 只能在资产类型为表时使用")
        if not isinstance(value, dict):
            raise invalid("filters", f"筛选维度 {dim} 的格式不正确")
        values = value.get("values") or []
        include_none = bool(value.get("includeNone", False))
        if not isinstance(values, list) or len(values) > MAX_VALUES:
            raise invalid("filters", f"筛选维度 {dim} 最多 {MAX_VALUES} 个取值")
        if any(not isinstance(v, str) or not v or len(v) > 256 for v in values):
            raise invalid("filters", f"筛选维度 {dim} 的取值不能为空")
        if include_none and dim not in NONE_DIMENSIONS:
            raise invalid("filters", f"筛选维度 {dim} 不支持「无」")
        if values or include_none:
            filters[dim] = (tuple(values), include_none)
    sort = raw.get("sort") or {}
    sort_field = sort.get("field", "popularity")
    sort_order = sort.get("order", "desc")
    if sort_field not in SORT_FIELDS:
        raise invalid("sort", f"不支持的排序：{sort_field}")
    if sort_order not in SORT_ORDERS:
        raise invalid("sort", f"不支持的排序方向：{sort_order}")
    page = raw.get("page", 1)
    page_size = raw.get("pageSize", 15)
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise invalid("page", "页码必须是大于 0 的整数")
    if page_size not in PAGE_SIZES:
        raise invalid("pageSize", "每页条数只能是 15、25 或 50")
    if (page - 1) * page_size + page_size > RESULT_WINDOW:
        raise ContextureError(
            "search.window_exceeded",
            f"只能浏览前 {RESULT_WINDOW} 条结果，请缩小条件",
            status_code=422,
            details={"field": "page"},
        )
    return Criteria(
        keyword=keyword,
        scope=scope,
        entity_type=entity_type,
        browse_path=parse_browse_path(raw.get("browsePath")),
        filters=filters,
        sort_field=sort_field,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


def escape_keyword(keyword: str) -> str:
    """关键词始终按普通文本处理（research R2）：转义 query_string 保留字符，大写运算符改小写。"""
    if not keyword:
        return "*"
    escaped = "".join(f"\\{ch}" if ch in _RESERVED else ch for ch in keyword)
    return _OPERATOR.sub(lambda m: m.group(1).lower(), escaped)


def index_for(c: Criteria) -> str:
    return c.entity_type or c.scope or "dataAsset"


def _browse_clauses(path: tuple[tuple[str, str], ...]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for level, value in path:
        if level == "root":
            children = BROWSE_ROOTS[value][1]
            out.append({"bool": {"should": [{"term": {"entityType": e}} for e in children]}})
        else:
            out.append({"term": {BROWSE_FIELDS[level][0]: value}})
    return out


def _filter_clauses(c: Criteria, exclude: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for dim, (values, include_none) in c.filters.items():
        if dim == exclude:
            continue
        es_field = FACETS[dim][0]
        should: list[dict[str, Any]] = [{"term": {es_field: v}} for v in values]
        if include_none:
            should.append({"bool": {"must_not": {"exists": {"field": es_field}}}})
        out.append({"bool": {"should": should}})
    return out


def build_query_filter(
    c: Criteria,
    *,
    exclude: str | None = None,
    browse: tuple[tuple[str, str], ...] | None = None,
) -> dict[str, Any]:
    """同一维度内为「或」，跨维度为「且」，与位置条件按「且」叠加；始终排除已软删除的实体。"""
    path = c.browse_path if browse is None else browse
    must = [{"term": {"deleted": False}}, *_browse_clauses(path), *_filter_clauses(c, exclude)]
    return {"query": {"bool": {"must": must}}}


def query_params(c: Criteria) -> dict[str, Any]:
    return {
        "q": escape_keyword(c.keyword),
        "index": index_for(c),
        "from": (c.page - 1) * c.page_size,
        "size": c.page_size,
        "query_filter": json.dumps(build_query_filter(c), ensure_ascii=False),
        "sort_field": SORT_FIELDS[c.sort_field],
        "sort_order": c.sort_order,
        "track_total_hits": "true",
        "deleted": "false",
    }


# ---------- 投影 ----------
def segments(fragment: str) -> list[dict[str, Any]]:
    """把 OM 高亮片段（HTML 已转义，命中词以 span 包裹）转为纯文本片段，不向浏览器输出 HTML。"""
    out: list[dict[str, Any]] = []
    pos = 0
    for m in _HIGHLIGHT.finditer(fragment):
        if m.start() > pos:
            out.append({"text": html.unescape(fragment[pos : m.start()]), "match": False})
        out.append({"text": html.unescape(m.group(1)), "match": True})
        pos = m.end()
    if pos < len(fragment):
        out.append({"text": html.unescape(fragment[pos:]), "match": False})
    return out


def matched_fields(highlight: Mapping[str, list[str]]) -> list[dict[str, Any]]:
    return [
        {"field": key, "count": len(frags)}
        for key, frags in highlight.items()
        if ".ngram" not in key and key not in _SKIP_HIGHLIGHT_KEYS
    ]


def _refs(items: Any) -> list[dict[str, Any]]:
    out = []
    for r in items or []:
        if isinstance(r, dict) and r.get("id") and r.get("type"):
            out.append(
                {
                    k: r[k]
                    for k in ("id", "type", "name", "displayName", "fullyQualifiedName")
                    if r.get(k) is not None
                }
            )
    return out


def governance(src: Mapping[str, Any]) -> dict[str, Any]:
    split = split_tags(src.get("tags"))
    cert = ((src.get("certification") or {}).get("tagLabel") or {}).get("tagFQN")
    tier = split.tier or ((src.get("tier") or {}).get("tagFQN") if src.get("tier") else None)
    return {
        "owners": _refs(src.get("owners")),
        "domains": _refs(src.get("domains")),
        "dataProducts": _refs(src.get("dataProducts")),
        "tier": tier,
        "dataLevel": split.data_level,
        "certification": cert,
        "glossaryTerms": split.glossary_terms,
        "tags": split.tags,
        "origin": split.origin,
    }


def _label(ref: Any) -> str | None:
    if not isinstance(ref, dict):
        return None
    value = ref.get("displayName") or ref.get("name")
    return str(value) if value else None


def breadcrumb(src: Mapping[str, Any]) -> list[dict[str, str]]:
    out = []
    for key in ("service", "database", "databaseSchema"):
        label = _label(src.get(key))
        if label:
            out.append(
                {"entityType": key if key != "service" else "databaseService", "label": label}
            )
    table = src.get("table")
    if src.get("entityType") == "tableColumn" and isinstance(table, dict):
        label = _label(table)
        if label:
            out.append({"entityType": "table", "label": label})
    return out


def _parent_table(src: Mapping[str, Any]) -> dict[str, Any] | None:
    table = src.get("table")
    if src.get("entityType") != "tableColumn" or not isinstance(table, dict):
        return None
    return {
        "entityType": "table",
        "id": str(table.get("id") or ""),
        "fqn": str(table.get("fullyQualifiedName") or ""),
    }


def project_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    src: Mapping[str, Any] = hit.get("_source") or {}
    hl: Mapping[str, list[str]] = hit.get("highlight") or {}
    gov = governance(src)
    # 标题显示 displayName；只有 displayName 缺失或与 name 相同时才用 name 的高亮
    display = src.get("displayName")
    name_hl = hl.get("name") if not display or display == src.get("name") else None
    name_frag = (hl.get("displayName") or name_hl or [None])[0]
    desc_frag = (hl.get("description") or [None])[0]
    is_column = src.get("entityType") == "tableColumn"
    return {
        "ref": {
            "entityType": src.get("entityType"),
            "id": str(src.get("id") or ""),
            "fqn": str(src.get("fullyQualifiedName") or ""),
        },
        "name": str(src.get("name") or ""),
        "displayName": src.get("displayName"),
        "serviceType": src.get("serviceType"),
        "breadcrumb": breadcrumb(src),
        "nameHighlight": segments(name_frag) if name_frag else [],
        "descriptionHighlight": segments(desc_frag) if desc_frag else [],
        "description": src.get("description"),
        "governance": gov,
        "origin": gov["origin"],
        "matchedFields": matched_fields(hl),
        "parentTable": _parent_table(src),
        "columnName": src.get("name") if is_column else None,
    }


def default_type(counts: list[dict[str, Any]], top_hit: str | None) -> str | None:
    """有关键词时默认选中首条命中结果的类型，否则选计数最多的类型（FR-007）。"""
    by_type = {c["entityType"]: c["count"] for c in counts}
    if top_hit and by_type.get(top_hit, 0) > 0:
        return top_hit
    if not counts:
        return None
    return str(max(counts, key=lambda c: c["count"])["entityType"])


def group_suggestions(hits: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        src: Mapping[str, Any] = hit.get("_source") or {}
        et = src.get("entityType")
        if et not in ENTITY_TYPES:
            continue
        items = groups.setdefault(str(et), [])
        if len(items) >= SUGGESTIONS_PER_TYPE:
            continue
        items.append(
            {
                "ref": {
                    "entityType": et,
                    "id": str(src.get("id") or ""),
                    "fqn": str(src.get("fullyQualifiedName") or ""),
                },
                "label": str(src.get("displayName") or src.get("name") or ""),
                "location": str(src.get("fullyQualifiedName") or ""),
                "parentTable": _parent_table(src),
                "columnName": src.get("name") if et == "tableColumn" else None,
            }
        )
    return [{"entityType": et, "items": items} for et, items in groups.items()]


def buckets(body: Mapping[str, Any], es_field: str) -> list[dict[str, Any]]:
    aggs: Mapping[str, Any] = body.get("aggregations") or {}
    agg = aggs.get(f"sterms#{es_field}") or aggs.get(es_field) or {}
    return list(agg.get("buckets") or [])


def bucket_label(bucket: Mapping[str, Any], label_field: str | None) -> str:
    """有 sourceFields 时，从 top_hits 中取原始大小写的显示名；没有时用桶键。"""
    if label_field:
        for key, value in bucket.items():
            if key.startswith("top_hits#") or key == "top":
                for h in (value.get("hits") or {}).get("hits") or []:
                    node: Any = h.get("_source") or {}
                    for part in label_field.split("."):
                        node = node[0] if isinstance(node, list) and node else node
                        node = node.get(part) if isinstance(node, dict) else None
                    if isinstance(node, list):
                        node = node[0] if node else None
                    if node:
                        return str(node)
    return str(bucket.get("key"))


# ---------- 快速筛选与浏览树（/search/aggregate） ----------
def _regex_contains(text: str) -> str:
    """选项内搜索：OM 以 include 正则匹配桶键（服务端转小写），这里转义 Lucene 正则保留字符。"""
    return ".*" + "".join(f"\\{ch}" if ch in _REGEX_RESERVED else ch for ch in text.lower()) + ".*"


def facet_params(c: Criteria, dimension: str, option_query: str | None = None) -> dict[str, Any]:
    if dimension not in FACETS:
        raise invalid("dimension", f"不支持的筛选维度：{dimension}")
    if dimension in TABLE_ONLY and index_for(c) != "table":
        raise invalid("dimension", f"筛选维度 {dimension} 只能在资产类型为表时使用")
    if option_query and len(option_query) > MAX_OPTION_QUERY:
        raise invalid("optionQuery", f"选项搜索最多 {MAX_OPTION_QUERY} 个字符")
    es_field, label_field = FACETS[dimension]
    params: dict[str, Any] = {
        "index": index_for(c),
        "field": es_field,
        "size": FACET_SIZE,
        "deleted": "false",
        # 本维度的选项计数排除本维度自身的已选条件（$UI/components/Explore/ExploreQuickFilters.tsx）
        "q": json.dumps(build_query_filter(c, exclude=dimension), ensure_ascii=False),
        "value": _regex_contains(option_query) if option_query else ".*",
    }
    if c.keyword:
        params["queryText"] = escape_keyword(c.keyword)
    if label_field:
        params["sourceFields"] = label_field
    return params


def facet_options(rows: list[dict[str, Any]], label_field: str | None) -> list[dict[str, Any]]:
    return [
        {
            "value": str(b["key"]),
            "label": bucket_label(b, label_field),
            "count": int(b.get("doc_count") or 0),
        }
        for b in rows
    ]


def browse_params(c: Criteria, parent: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    """浏览树的一层（research R3）：根层聚合 entityType；其下按大类的层级依次展开。"""
    params: dict[str, Any] = {
        "index": "dataAsset",
        "size": BROWSE_BUCKETS,
        "deleted": "false",
        "value": ".*",
        "q": json.dumps(build_query_filter(c, browse=parent), ensure_ascii=False),
    }
    if c.keyword:
        params["queryText"] = escape_keyword(c.keyword)
    if not parent:
        params["field"] = "entityType"
        return params
    levels = BROWSE_ROOTS[parent[0][1]][2]
    depth = len(parent) - 1
    if depth >= len(levels):
        raise invalid("parentPath", "该节点没有下一层")
    es_field, label_field = BROWSE_FIELDS[levels[depth]]
    params["field"] = es_field
    if label_field:
        params["sourceFields"] = label_field
    return params


def browse_nodes(
    parent: tuple[tuple[str, str], ...], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not parent:
        counts = {str(b["key"]): int(b.get("doc_count") or 0) for b in rows}
        nodes = []
        for key, (label, children, _levels) in BROWSE_ROOTS.items():
            total = sum(counts.get(e, 0) for e in children)
            if total > 0:  # 计数为 0 的根节点不显示（FR-006）
                nodes.append(
                    {
                        "level": "root",
                        "value": key,
                        "label": label,
                        "count": total,
                        "hasChildren": True,
                    }
                )
        return nodes
    levels = BROWSE_ROOTS[parent[0][1]][2]
    level = levels[len(parent) - 1]
    label_field = BROWSE_FIELDS[level][1]
    return [
        {
            "level": level,
            "value": str(b["key"]),
            "label": bucket_label(b, label_field),
            "count": int(b.get("doc_count") or 0),
            "hasChildren": level != "entityType",
        }
        for b in rows
        if int(b.get("doc_count") or 0) > 0
    ]


# ---------- 调用 OM ----------
async def search_request(
    om: OmClient, ctx: RequestContext, path: str, params: dict[str, Any]
) -> dict[str, Any]:
    """调用 OM /v1/search/*，把索引缺失与超时映射为 006 错误码（research R11）。"""
    try:
        body = await om.request(ctx, "GET", path, params=params)
    except UpstreamUnavailable as exc:
        message = str((exc.details or {}).get("message") or "")
        if message.startswith(INDEX_MISSING_PREFIX):
            raise ContextureError(
                "search.index_missing",
                f"OpenMetadata 搜索索引缺失：{message}",
                status_code=503,
                details={"upstream": "openmetadata"},
            ) from exc
        raise
    if isinstance(body, dict) and body.get("timed_out") is True:
        raise ContextureError(
            "search.timeout",
            "OpenMetadata 搜索超时（30 秒），未返回完整结果",
            status_code=504,
            details={"upstream": "openmetadata"},
        )
    return body if isinstance(body, dict) else {}


def _total(body: Mapping[str, Any]) -> int:
    total = (body.get("hits") or {}).get("total")
    if isinstance(total, dict):
        return int(total.get("value") or 0)
    return int(total or 0)


class SearchService:
    def __init__(self, om: OmClient) -> None:
        self.om = om

    async def search(self, ctx: RequestContext, raw: Mapping[str, Any]) -> dict[str, Any]:
        c = parse_criteria(raw)
        params = query_params(c)
        body = await search_request(self.om, ctx, "/search/query", params)
        total = _total(body)
        hits = [project_hit(h) for h in (body.get("hits") or {}).get("hits") or []]
        return {
            "total": total,
            "page": c.page,
            "pageSize": c.page_size,
            "windowLimited": total > RESULT_WINDOW,
            "index": params["index"],
            "hits": hits,
        }

    async def type_counts(self, ctx: RequestContext, raw: Mapping[str, Any]) -> dict[str, Any]:
        """按类型计数（/entityTypeCounts）与首条命中结果的类型（size=1 的 /query），两者并行。"""
        c = parse_criteria({**raw, "entityType": None, "scope": None, "page": 1, "pageSize": 15})
        q = escape_keyword(c.keyword)
        query_filter = json.dumps(build_query_filter(c), ensure_ascii=False)
        counts_body, top_body = await asyncio.gather(
            search_request(
                self.om,
                ctx,
                "/search/entityTypeCounts",
                {"q": q, "index": "dataAsset", "query_filter": query_filter},
            ),
            search_request(
                self.om,
                ctx,
                "/search/query",
                {
                    "q": q,
                    "index": "dataAsset",
                    "size": 1,
                    "query_filter": query_filter,
                    "include_source_fields": ["entityType"],
                    "deleted": "false",
                },
            ),
        )
        counts = [
            {"entityType": b["key"], "count": int(b["doc_count"])}
            for b in buckets(counts_body, "entityType")
            if b.get("key") in ENTITY_TYPES and int(b.get("doc_count") or 0) > 0
        ]
        counts.sort(key=lambda x: (-x["count"], x["entityType"]))
        top_hits = (top_body.get("hits") or {}).get("hits") or []
        top = (top_hits[0].get("_source") or {}).get("entityType") if top_hits else None
        return {"counts": counts, "topHitType": top, "defaultType": default_type(counts, top)}

    async def facets(
        self,
        ctx: RequestContext,
        raw: Mapping[str, Any],
        dimension: str,
        option_query: str | None = None,
    ) -> dict[str, Any]:
        c = parse_criteria(raw)
        params = facet_params(c, dimension, option_query)
        body = await search_request(self.om, ctx, "/search/aggregate", params)
        return {
            "dimension": dimension,
            "supportsNone": dimension in NONE_DIMENSIONS,
            "options": facet_options(buckets(body, params["field"]), FACETS[dimension][1]),
        }

    async def browse(
        self, ctx: RequestContext, raw: Mapping[str, Any], parent_raw: Any
    ) -> dict[str, Any]:
        c = parse_criteria({**raw, "browsePath": []})
        parent = parse_browse_path(parent_raw, "parentPath", limit=5)
        params = browse_params(c, parent)
        body = await search_request(self.om, ctx, "/search/aggregate", params)
        return {"nodes": browse_nodes(parent, buckets(body, params["field"]))}

    async def suggestions(
        self, ctx: RequestContext, keyword: str, scope: str | None
    ) -> dict[str, Any]:
        c = parse_criteria({"keyword": keyword, "scope": scope})
        if not c.keyword:
            raise invalid("keyword", "关键词不能为空")
        body = await search_request(
            self.om,
            ctx,
            "/search/query",
            {
                "q": escape_keyword(c.keyword),
                "index": index_for(c),
                "size": SUGGESTION_SIZE,
                "deleted": "false",
                "query_filter": json.dumps(build_query_filter(c), ensure_ascii=False),
                "include_source_fields": SUGGESTION_FIELDS,
            },
        )
        return {"groups": group_suggestions((body.get("hits") or {}).get("hits") or [])}
