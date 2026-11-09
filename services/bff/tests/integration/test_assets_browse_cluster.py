"""US2 集成（真实 OM，-m cluster）：组合条件与 OM 一致（SC-004）；浏览树定位每张表（SC-001）。"""

import asyncio
import json
from typing import Any

import pytest
from cluster_assets import CTX, MARKER, TABLES, dev_filter, om

pytestmark = pytest.mark.cluster
DELETED = {"term": {"deleted": False}}
DEV = {"bool": {"should": [{"term": {"tags.tagFQN": MARKER.lower()}}]}}


async def _direct(
    client: Any, must: list[dict[str, Any]], index: str = "table"
) -> tuple[int, set[str]]:
    body = await client.request(
        CTX,
        "GET",
        "/search/query",
        params={
            "q": "*",
            "index": index,
            "size": 100,
            "deleted": "false",
            "track_total_hits": "true",
            "query_filter": json.dumps({"query": {"bool": {"must": [DELETED, DEV, *must]}}}),
        },
    )
    return body["hits"]["total"]["value"], {h["_source"]["id"] for h in body["hits"]["hits"]}


async def _ours(svc: Any, raw: dict[str, Any]) -> tuple[int, set[str]]:
    page = await svc.search(CTX, {"entityType": "table", "pageSize": 50, **raw})
    return page["total"], {h["ref"]["id"] for h in page["hits"]}


CASES = [
    ("关键词", {"keyword": "employee"}, None),
    (
        "位置",
        {
            "browsePath": [
                {"level": "root", "value": "databases"},
                {"level": "serviceType", "value": "mysql"},
                {"level": "service", "value": "devtest-mes"},
                {"level": "database", "value": "default"},
                {"level": "databaseSchema", "value": "mes"},
            ]
        },
        [
            {"term": {"service.displayName": "devtest-mes"}},
            {"term": {"databaseSchema.displayName": "mes"}},
        ],
    ),
    (
        "同维度多选",
        {"filters": dev_filter({"tier": {"values": ["tier.tier1", "tier.tier2"]}})},
        [
            {
                "bool": {
                    "should": [
                        {"term": {"tier.tagFQN": "tier.tier1"}},
                        {"term": {"tier.tagFQN": "tier.tier2"}},
                    ]
                }
            }
        ],
    ),
    (
        "跨维度组合",
        {
            "filters": dev_filter(
                {"tier": {"values": ["tier.tier1"]}, "domain": {"values": ["开发态-生产域"]}}
            )
        },
        [
            {"bool": {"should": [{"term": {"tier.tagFQN": "tier.tier1"}}]}},
            {"bool": {"should": [{"term": {"domains.displayName.keyword": "开发态-生产域"}}]}},
        ],
    ),
    (
        "无负责人",
        {"filters": dev_filter({"owner": {"values": [], "includeNone": True}})},
        [{"bool": {"should": [{"bool": {"must_not": {"exists": {"field": "ownerDisplayName"}}}}]}}],
    ),
]


@pytest.mark.parametrize("name,raw,must", CASES, ids=[c[0] for c in CASES])
def test_combinations_equal_direct_om(
    name: str, raw: dict[str, Any], must: list[dict[str, Any]] | None
) -> None:
    async def run() -> None:
        with om() as (svc, _, client):
            criteria = {**raw}
            criteria.setdefault("filters", dev_filter())
            ours = await _ours(svc, criteria)
            if must is None:
                body = await client.request(
                    CTX,
                    "GET",
                    "/search/query",
                    params={
                        "q": raw["keyword"],
                        "index": "table",
                        "size": 100,
                        "deleted": "false",
                        "track_total_hits": "true",
                        "query_filter": json.dumps({"query": {"bool": {"must": [DELETED, DEV]}}}),
                    },
                )
                direct = (
                    body["hits"]["total"]["value"],
                    {h["_source"]["id"] for h in body["hits"]["hits"]},
                )
            else:
                direct = await _direct(client, must)
            assert ours == direct, name
            assert ours[0] > 0, f"{name}：fixture 应至少命中一张表"

    asyncio.run(run())


def test_browse_tree_reaches_every_fixture_table_and_counts_match() -> None:
    async def run() -> None:
        with om() as (svc, _, client):
            crit = {"filters": dev_filter()}
            roots = (await svc.browse(CTX, crit, []))["nodes"]
            db_root = next(n for n in roots if n["value"] == "databases")
            for t in TABLES:
                svc_name, db, schema = t.fqn.split(".")[:3]
                path: list[dict[str, str]] = [{"level": "root", "value": "databases"}]
                for level, value in [
                    ("serviceType", None),
                    ("service", svc_name),
                    ("database", db),
                    ("databaseSchema", schema),
                ]:
                    nodes = (await svc.browse(CTX, crit, path))["nodes"]
                    if value is None:
                        stype = {
                            "devtest-mes": "mysql",
                            "devtest-qms": "postgres",
                            "devtest-dw": "doris",
                        }[svc_name]
                        node = next(n for n in nodes if n["value"] == stype)
                    else:
                        node = next(n for n in nodes if n["value"] == value)
                    path.append({"level": level, "value": node["value"]})
                page = await svc.search(
                    CTX,
                    {
                        "browsePath": path,
                        "entityType": "table",
                        "filters": crit["filters"],
                        "pageSize": 50,
                    },
                )
                assert t.fqn in {h["ref"]["fqn"] for h in page["hits"]}, t.fqn
            direct_db = await client.request(
                CTX,
                "GET",
                "/search/aggregate",
                params={
                    "index": "dataAsset",
                    "field": "entityType",
                    "value": ".*",
                    "size": 100,
                    "deleted": "false",
                    "q": json.dumps({"query": {"bool": {"must": [DELETED, DEV]}}}),
                },
            )
            counts = {
                b["key"]: b["doc_count"]
                for b in direct_db["aggregations"]["sterms#entityType"]["buckets"]
            }
            expected = sum(
                counts.get(e, 0)
                for e in ("database", "databaseSchema", "storedProcedure", "table", "tableColumn")
            )
            assert db_root["count"] == expected

    asyncio.run(run())


def test_facet_counts_exclude_own_dimension() -> None:
    async def run() -> None:
        with om() as (svc, _, _):
            raw = {
                "entityType": "table",
                "filters": dev_filter({"tier": {"values": ["tier.tier1"]}}),
            }
            facet = await svc.facets(CTX, raw, "tier")
            values = {o["value"] for o in facet["options"]}
            assert {"tier.tier1", "tier.tier2"} <= values, values

    asyncio.run(run())
