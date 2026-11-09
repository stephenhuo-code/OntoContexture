"""006 浏览树：大类、层级字段、根计数求和、父路径过滤（research R3；FR-006）。"""

import json

import pytest

from contexture_bff.adapters.om_search import (
    BROWSE_ROOTS,
    browse_nodes,
    browse_params,
    parse_browse_path,
    parse_criteria,
)
from contexture_core.errors import ContextureError


def _p(*steps: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(steps)


def test_roots_follow_om_explore_tree() -> None:
    assert BROWSE_ROOTS["databases"][1] == (
        "database",
        "databaseSchema",
        "storedProcedure",
        "table",
        "tableColumn",
    )
    assert BROWSE_ROOTS["governance"][1] == ("tag", "glossaryTerm", "metric")
    assert BROWSE_ROOTS["databases"][2] == (
        "serviceType",
        "service",
        "database",
        "databaseSchema",
        "entityType",
    )
    assert BROWSE_ROOTS["dashboards"][2] == ("serviceType", "service", "entityType")
    assert BROWSE_ROOTS["governance"][2] == ("entityType",)


def test_root_level_aggregates_entity_type_over_data_assets() -> None:
    p = browse_params(parse_criteria({}), ())
    assert (p["index"], p["field"], p["value"], p["deleted"]) == (
        "dataAsset",
        "entityType",
        ".*",
        "false",
    )
    assert p["size"] == 1000
    assert "queryText" not in p


def test_root_counts_are_summed_and_zero_roots_hidden() -> None:
    buckets = [
        {"key": "table", "doc_count": 3},
        {"key": "tableColumn", "doc_count": 10},
        {"key": "glossaryTerm", "doc_count": 2},
        {"key": "chart", "doc_count": 0},
    ]
    nodes = browse_nodes((), buckets)
    assert [(n["value"], n["count"]) for n in nodes] == [("databases", 13), ("governance", 2)]
    assert nodes[0]["label"] == "数据库" and nodes[0]["hasChildren"] is True


@pytest.mark.parametrize(
    "parent,field",
    [
        (_p(("root", "databases")), "serviceType"),
        (_p(("root", "databases"), ("serviceType", "mysql")), "service.displayName"),
        (
            _p(("root", "databases"), ("serviceType", "mysql"), ("service", "devtest-mes")),
            "database.displayName",
        ),
        (
            _p(
                ("root", "databases"),
                ("serviceType", "mysql"),
                ("service", "devtest-mes"),
                ("database", "default"),
            ),
            "databaseSchema.displayName",
        ),
        (_p(("root", "governance")), "entityType"),
    ],
)
def test_next_level_field(parent: tuple[tuple[str, str], ...], field: str) -> None:
    assert browse_params(parse_criteria({}), parent)["field"] == field


def test_child_filter_contains_root_types_and_parent_terms() -> None:
    parent = _p(("root", "databases"), ("serviceType", "mysql"), ("service", "devtest-mes"))
    q = json.loads(
        browse_params(parse_criteria({"filters": {"tier": {"values": ["tier.tier1"]}}}), parent)[
            "q"
        ]
    )
    must = q["query"]["bool"]["must"]
    assert {"term": {"deleted": False}} in must
    assert {"term": {"serviceType": "mysql"}} in must
    assert {"term": {"service.displayName": "devtest-mes"}} in must
    root = next(
        c
        for c in must
        if "bool" in c and any("entityType" in s["term"] for s in c["bool"]["should"])
    )
    assert [s["term"]["entityType"] for s in root["bool"]["should"]] == list(
        BROWSE_ROOTS["databases"][1]
    )
    assert {"bool": {"should": [{"term": {"tier.tagFQN": "tier.tier1"}}]}} in must


def test_child_nodes_and_leaf() -> None:
    parent = _p(("root", "databases"), ("serviceType", "mysql"))
    nodes = browse_nodes(parent, [{"key": "devtest-mes", "doc_count": 14}])
    assert nodes == [
        {
            "level": "service",
            "value": "devtest-mes",
            "label": "devtest-mes",
            "count": 14,
            "hasChildren": True,
        }
    ]
    leaf = browse_nodes(_p(("root", "governance")), [{"key": "glossaryTerm", "doc_count": 3}])
    assert leaf[0]["level"] == "entityType" and leaf[0]["hasChildren"] is False


def test_service_type_label_from_top_hits() -> None:
    nodes = browse_nodes(
        _p(("root", "databases")),
        [
            {
                "key": "mysql",
                "doc_count": 4,
                "top_hits#top": {"hits": {"hits": [{"_source": {"serviceType": "Mysql"}}]}},
            }
        ],
    )
    assert nodes[0]["label"] == "Mysql"


@pytest.mark.parametrize(
    "raw",
    [
        [{"level": "serviceType", "value": "x"}],
        [{"level": "root", "value": "nope"}],
        [{"level": "root", "value": "databases"}, {"level": "service", "value": "x"}],
        [
            {"level": "root", "value": "databases"},
            {"level": "serviceType", "value": "x"},
            {"level": "service", "value": "y"},
            {"level": "entityType", "value": "table"},
        ],
        [{"level": "root", "value": "governance"}, {"level": "serviceType", "value": "x"}],
    ],
)
def test_invalid_paths(raw: list[dict[str, str]]) -> None:
    with pytest.raises(ContextureError) as ei:
        parse_browse_path(raw)
    assert ei.value.code == "search.invalid_criteria"


def test_leaf_has_no_children_to_browse() -> None:
    with pytest.raises(ContextureError):
        browse_params(parse_criteria({}), _p(("root", "governance"), ("entityType", "tag")))
