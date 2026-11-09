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
