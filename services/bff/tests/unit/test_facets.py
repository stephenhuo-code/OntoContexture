"""006 快速筛选：字段映射、排除本维度、「无」、选项内搜索、显示名（research R4；FR-008）。"""

import json

import pytest

from contexture_bff.adapters.om_search import (
    FACETS,
    NONE_DIMENSIONS,
    facet_options,
    facet_params,
    parse_criteria,
)
from contexture_core.errors import ContextureError


def test_field_mapping_matches_research_r4() -> None:
    assert {k: v[0] for k, v in FACETS.items()} == {
        "entityType": "entityType",
        "domain": "domains.displayName.keyword",
        "dataProduct": "dataProducts.displayName.keyword",
        "owner": "ownerDisplayName",
        "tag": "tags.tagFQN",
        "tier": "tier.tagFQN",
        "service": "service.displayName.keyword",
        "serviceType": "serviceType",
        "certification": "certification.tagLabel.tagFQN",
        "database": "database.displayName.keyword",
        "databaseSchema": "databaseSchema.displayName.keyword",
        "column": "columns.name.keyword",
        "tableType": "tableType",
        "columnDescriptionStatus": "columnDescriptionStatus",
    }
    assert {"owner", "domain", "tier", "tag", "certification"} == NONE_DIMENSIONS


def test_counts_exclude_own_dimension_but_keep_others() -> None:
    c = parse_criteria(
        {
            "keyword": "工单",
            "browsePath": [{"level": "root", "value": "databases"}],
            "filters": {
                "tier": {"values": ["tier.tier1", "tier.tier2"]},
                "owner": {"values": [], "includeNone": True},
            },
        }
    )
    p = facet_params(c, "tier")
    must = json.loads(p["q"])["query"]["bool"]["must"]
    assert not any("tier.tagFQN" in json.dumps(m) for m in must)
    assert {
        "bool": {"should": [{"bool": {"must_not": {"exists": {"field": "ownerDisplayName"}}}}]}
    } in must
    assert p["queryText"] == "工单"
    assert (p["field"], p["size"], p["deleted"], p["value"]) == ("tier.tagFQN", 10, "false", ".*")
    own = json.loads(facet_params(c, "owner")["q"])["query"]["bool"]["must"]
    assert {
        "bool": {
            "should": [
                {"term": {"tier.tagFQN": "tier.tier1"}},
                {"term": {"tier.tagFQN": "tier.tier2"}},
            ]
        }
    } in own


def test_option_query_is_escaped_contains_regex() -> None:
    p = facet_params(parse_criteria({}), "domain", "生产.域(1)")
    assert p["value"] == r".*生产\.域\(1\).*"
    assert p["sourceFields"] == "domains.displayName"


def test_table_only_dimensions_require_table_type() -> None:
    with pytest.raises(ContextureError) as ei:
        facet_params(parse_criteria({}), "column")
    assert ei.value.code == "search.invalid_criteria"
    assert facet_params(parse_criteria({"entityType": "table"}), "column")["index"] == "table"


def test_options_labels_and_order() -> None:
    buckets = [
        {
            "key": "开发态-生产域",
            "doc_count": 3,
            "top_hits#top": {
                "hits": {"hits": [{"_source": {"domains": [{"displayName": "开发态-生产域"}]}}]}
            },
        },
        {"key": "tier.tier1", "doc_count": 2},
    ]
    assert facet_options(buckets, "domains.displayName") == [
        {"value": "开发态-生产域", "label": "开发态-生产域", "count": 3},
        {"value": "tier.tier1", "label": "tier.tier1", "count": 2},
    ]
