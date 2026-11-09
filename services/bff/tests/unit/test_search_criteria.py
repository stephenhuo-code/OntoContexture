"""006 条件翻译：SearchCriteria → OM /v1/search/query 参数（research R2、R5；FR-019）。"""

import json

import pytest

from contexture_bff.adapters.om_search import (
    ENTITY_TYPES,
    SORT_FIELDS,
    build_query_filter,
    escape_keyword,
    index_for,
    parse_criteria,
    query_params,
)
from contexture_core.errors import ContextureError


def _err(raw: dict) -> ContextureError:
    with pytest.raises(ContextureError) as ei:
        parse_criteria(raw)
    return ei.value


def test_defaults() -> None:
    c = parse_criteria({})
    assert (c.keyword, c.scope, c.entity_type, c.page, c.page_size) == ("", None, None, 1, 15)
    assert (c.sort_field, c.sort_order) == ("popularity", "desc")


def test_keyword_trim_length_and_match_all() -> None:
    assert parse_criteria({"keyword": "  工单  "}).keyword == "工单"
    assert escape_keyword("") == "*"
    assert _err({"keyword": "x" * 201}).code == "search.invalid_criteria"


@pytest.mark.parametrize("ch", list('+-=&|><!(){}[]^"~*?:\\/'))
def test_reserved_characters_are_escaped(ch: str) -> None:
    assert escape_keyword(f"a{ch}b") == f"a\\{ch}b"


def test_uppercase_operators_become_plain_words() -> None:
    assert escape_keyword("work AND order OR NOT x") == "work and order or not x"
    assert escape_keyword("ANDROID") == "ANDROID"


def test_index_priority_and_whitelist() -> None:
    assert index_for(parse_criteria({})) == "dataAsset"
    assert index_for(parse_criteria({"scope": "glossaryTerm"})) == "glossaryTerm"
    assert index_for(parse_criteria({"scope": "table", "entityType": "table"})) == "table"
    assert len(ENTITY_TYPES) == 24 and "tableColumn" in ENTITY_TYPES
    assert _err({"scope": "databaseService"}).code == "search.invalid_criteria"
    assert _err({"scope": "table", "entityType": "tag"}).details["field"] == "entityType"


def test_query_filter_always_excludes_deleted() -> None:
    must = build_query_filter(parse_criteria({}))["query"]["bool"]["must"]
    assert {"term": {"deleted": False}} in must


def test_sort_mapping_and_params() -> None:
    assert SORT_FIELDS == {
        "popularity": "totalVotes",
        "name": "displayName.keyword",
        "relevance": "_score",
        "updatedAt": "updatedAt",
    }
    c = parse_criteria(
        {"keyword": "工单", "sort": {"field": "name", "order": "asc"}, "page": 3, "pageSize": 25}
    )
    p = query_params(c)
    assert p["q"] == "工单"
    assert p["index"] == "dataAsset"
    assert (p["from"], p["size"]) == (50, 25)
    assert (p["sort_field"], p["sort_order"]) == ("displayName.keyword", "asc")
    assert p["deleted"] == "false" and p["track_total_hits"] == "true"
    assert json.loads(p["query_filter"])["query"]["bool"]["must"][0] == {"term": {"deleted": False}}


@pytest.mark.parametrize("size", [0, 20, 100])
def test_page_size_whitelist(size: int) -> None:
    assert _err({"pageSize": size}).details["field"] == "pageSize"


def test_result_window() -> None:
    assert parse_criteria({"page": 200, "pageSize": 50}).page == 200
    e = _err({"page": 668, "pageSize": 15})
    assert (e.code, e.status_code) == ("search.window_exceeded", 422)
    assert _err({"page": 0}).code == "search.invalid_criteria"
