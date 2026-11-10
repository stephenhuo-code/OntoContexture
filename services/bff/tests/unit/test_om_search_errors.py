"""006：OM 搜索错误的识别与映射（research R11）。错误体符合 contracts/schemas/error.json。"""

import httpx
import pytest
from bff_fakes import user_context

from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_search import search_request
from contexture_core.errors import ContextureError, UpstreamUnavailable


class Ex:
    async def exchange(self, subject_token: str, audience: str) -> str:
        return "om-token"


def _client(handler: httpx.MockTransport) -> OmClient:
    return OmClient(
        om_url="http://om:8585", exchanger=Ex(), http=httpx.AsyncClient(transport=handler)
    )


async def test_index_missing_is_503_search_index_missing() -> None:
    om = _client(
        httpx.MockTransport(
            lambda r: httpx.Response(
                500, json={"code": 500, "message": "Failed to find index table_search_index"}
            )
        )
    )
    with pytest.raises(ContextureError) as ei:
        await search_request(om, user_context(), "/search/query", {"q": "*"})
    assert ei.value.code == "search.index_missing"
    assert ei.value.status_code == 503


async def test_timed_out_is_504_without_partial_results() -> None:
    om = _client(
        httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"timed_out": True, "hits": {"total": {"value": 3}, "hits": [{}]}}
            )
        )
    )
    with pytest.raises(ContextureError) as ei:
        await search_request(om, user_context(), "/search/query", {"q": "*"})
    assert ei.value.code == "search.timeout"
    assert ei.value.status_code == 504


async def test_other_5xx_is_upstream_unavailable() -> None:
    om = _client(
        httpx.MockTransport(
            lambda r: httpx.Response(500, json={"message": "Search failed due to x"})
        )
    )
    with pytest.raises(UpstreamUnavailable):
        await search_request(om, user_context(), "/search/query", {"q": "*"})


async def test_connection_error_is_upstream_unavailable() -> None:
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    om = _client(httpx.MockTransport(boom))
    with pytest.raises(UpstreamUnavailable):
        await search_request(om, user_context(), "/search/query", {"q": "*"})


async def test_success_returns_body() -> None:
    body = {"timed_out": False, "hits": {"total": {"value": 0}, "hits": []}}
    om = _client(httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    assert await search_request(om, user_context(), "/search/query", {"q": "*"}) == body
