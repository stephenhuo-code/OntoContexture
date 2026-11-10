"""US1 集成（真实 OM，-m cluster）：搜索、类型计数、同名可辨、查询语法字符（SC-001、SC-005）。"""

import asyncio
import json

import pytest
from cluster_assets import CTX, MARKER, TABLES, dev_filter, om

pytestmark = pytest.mark.cluster


def test_every_fixture_table_is_found_by_english_name() -> None:
    async def run() -> None:
        with om() as (svc, _, _):
            for t in TABLES:
                page = await svc.search(
                    CTX,
                    {
                        "keyword": t.body["name"],
                        "entityType": "table",
                        "filters": dev_filter(),
                        "pageSize": 50,
                    },
                )
                fqns = {h["ref"]["fqn"] for h in page["hits"]}
                assert t.fqn in fqns, t.fqn

    asyncio.run(run())


def test_type_counts_equal_direct_om_counts() -> None:
    async def run() -> None:
        with om() as (svc, _, client):
            ours = await svc.type_counts(CTX, {"keyword": "工单", "filters": dev_filter()})
            direct = await client.request(
                CTX,
                "GET",
                "/search/entityTypeCounts",
                params={
                    "q": "工单",
                    "index": "dataAsset",
                    "query_filter": json.dumps(
                        {
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"deleted": False}},
                                        {
                                            "bool": {
                                                "should": [
                                                    {"term": {"tags.tagFQN": MARKER.lower()}}
                                                ]
                                            }
                                        },
                                    ]
                                }
                            }
                        }
                    ),
                },
            )
            buckets = direct["aggregations"]["sterms#entityType"]["buckets"]
            assert {c["entityType"]: c["count"] for c in ours["counts"]} == {
                b["key"]: b["doc_count"] for b in buckets if b["doc_count"] > 0
            }
            assert ours["defaultType"] in {c["entityType"] for c in ours["counts"]}

    asyncio.run(run())


def test_same_name_tables_have_distinct_breadcrumbs() -> None:
    async def run() -> None:
        with om() as (svc, _, _):
            page = await svc.search(
                CTX, {"keyword": "work_order", "entityType": "table", "filters": dev_filter()}
            )
            crumbs = {
                " / ".join(b["label"] for b in h["breadcrumb"])
                for h in page["hits"]
                if h["name"] == "work_order"
            }
            assert len(crumbs) >= 2, crumbs

    asyncio.run(run())


@pytest.mark.parametrize(
    "keyword",
    [
        "work_order (",
        'work_order "',
        "work_order:",
        "work AND order",
        "NOT work_order",
        "work_order*?",
    ],
)
def test_query_syntax_characters_do_not_break_search(keyword: str) -> None:
    async def run() -> None:
        with om() as (svc, _, _):
            page = await svc.search(
                CTX, {"keyword": keyword, "entityType": "table", "filters": dev_filter()}
            )
            assert page["total"] >= 0
            # 筛选没有被静默忽略：结果全部带开发态标识
            assert all(h["origin"] == "devTest" for h in page["hits"])

    asyncio.run(run())
