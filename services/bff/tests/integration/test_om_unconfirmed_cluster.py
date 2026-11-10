"""research 中 UNCONFIRMED 的 OM 行为实测（-m cluster）；结论回写 research 与 acceptance。"""

import asyncio

import pytest
from cluster_assets import CTX, om

from contexture_core.errors import ContextureError, UpstreamUnavailable

pytestmark = pytest.mark.cluster


def test_result_window() -> None:
    """from + size 超过 10000：OM 返回 500（Result window is too large）；BFF 先行返回 422。"""

    async def run() -> None:
        with om() as (svc, _, client):
            with pytest.raises(UpstreamUnavailable) as ei:
                await client.request(
                    CTX,
                    "GET",
                    "/search/query",
                    params={"q": "*", "index": "dataAsset", "from": 9995, "size": 15},
                )
            message = str((ei.value.details or {}).get("message"))
            print(f"\n[006 实测] from=9995,size=15 → HTTP 500：{message[:160]}")
            assert "Result window is too large" in message
            with pytest.raises(ContextureError) as bff:
                await svc.search(CTX, {"page": 668, "pageSize": 15})
            assert bff.value.code == "search.window_exceeded"

    asyncio.run(run())


def test_timeout_shape() -> None:
    """本地数据量下无法让 OpenSearch 在 30 秒内超时；记录一次大窗口查询的 timed_out 取值。"""

    async def run() -> None:
        with om() as (_, _, client):
            body = await client.request(
                CTX,
                "GET",
                "/search/query",
                params={"q": "*", "index": "dataAsset", "size": 10000, "track_total_hits": "true"},
            )
            print(f"\n[006 实测] timed_out={body.get('timed_out')} took={body.get('took')}ms")
            assert body.get("timed_out") is False

    asyncio.run(run())


@pytest.mark.parametrize("collection", ["databases", "databaseSchemas"])
def test_certification_field(collection: str) -> None:
    """库与 Schema 是否接受 fields=certification（research R9）。"""

    async def run() -> None:
        with om() as (_, _, client):
            page = await client.request(CTX, "GET", f"/{collection}", params={"limit": 1})
            fqn = page["data"][0]["fullyQualifiedName"]
            entity = await client.request(
                CTX, "GET", f"/{collection}/name/{fqn}", params={"fields": "owners,certification"}
            )
            print(
                f"\n[006 实测] {collection} 接受 certification，返回键：{'certification' in entity}"
            )
            assert entity["fullyQualifiedName"] == fqn

    asyncio.run(run())


def test_display_name_fallback_and_raw_keyword_aggregation() -> None:
    """无 displayName 的实体回退为 name；database.displayName 可直接聚合（research R3）。"""

    async def run() -> None:
        with om() as (svc, _, client):
            body = await client.request(
                CTX,
                "GET",
                "/search/query",
                params={"q": "supplier", "index": "table", "size": 20, "deleted": "false"},
            )
            src = next(
                h["_source"]
                for h in body["hits"]["hits"]
                if h["_source"]["fullyQualifiedName"] == "devtest-mes.default.mes.supplier"
            )
            print(f"\n[006 实测] 无显示名的表 displayName={src.get('displayName')!r}")
            assert src.get("displayName") == "supplier"
            nodes = (
                await svc.browse(
                    CTX,
                    {},
                    [
                        {"level": "root", "value": "databases"},
                        {"level": "serviceType", "value": "mysql"},
                        {"level": "service", "value": "devtest-mes"},
                    ],
                )
            )["nodes"]
            print(f"[006 实测] database.displayName 聚合桶：{[n['value'] for n in nodes]}")
            assert "default" in {n["value"] for n in nodes}

    asyncio.run(run())


def test_facet_option_size_default() -> None:
    """OM UI 的 Explore 快速筛选不传 size，使用服务端默认 10；BFF 与之一致。"""
    from contexture_bff.adapters.om_search import FACET_SIZE

    assert FACET_SIZE == 10
