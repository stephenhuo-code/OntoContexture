"""OM 客户端（005）：以用户委托令牌调用 OM；错误如实映射，不回退任何数据；响应中的密码一律掩码。"""

import json

import httpx
import pytest
from bff_fakes import user_context

from contexture_bff.adapters.om_client import MASK, OmClient
from contexture_core.errors import ContextureError


class FakeExchanger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def exchange(self, subject_token: str, audience: str) -> str:
        self.calls.append((subject_token, audience))
        return "om-token"


def client(handler: httpx.MockTransport) -> tuple[OmClient, FakeExchanger]:
    ex = FakeExchanger()
    om = OmClient(
        om_url="http://om:8585",
        exchanger=ex,
        http=httpx.AsyncClient(transport=handler),
    )
    return om, ex


async def test_uses_delegated_token_for_openmetadata_audience() -> None:
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"data": []})

    om, ex = client(httpx.MockTransport(handler))
    assert await om.request(user_context(token="user-token"), "GET", "/services/databaseServices") == {
        "data": []
    }
    assert ex.calls == [("user-token", "contexture-openmetadata")]
    assert seen == {
        "auth": "Bearer om-token",
        "url": "http://om:8585/api/v1/services/databaseServices",
    }


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_server_error_maps_to_upstream_unavailable(status: int) -> None:
    om, _ = client(httpx.MockTransport(lambda req: httpx.Response(status, text="boom")))
    with pytest.raises(ContextureError) as exc:
        await om.request(user_context(), "GET", "/services/databaseServices")
    assert exc.value.code == "upstream.unavailable"
    assert exc.value.status_code == 502


async def test_connection_failure_maps_to_upstream_unavailable() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    om, _ = client(httpx.MockTransport(handler))
    with pytest.raises(ContextureError) as exc:
        await om.request(user_context(), "GET", "/tables")
    assert exc.value.code == "upstream.unavailable"


async def test_forbidden_maps_to_permission_error_with_om_message() -> None:
    body = {"code": 403, "message": "operations [Create] not allowed"}
    om, _ = client(httpx.MockTransport(lambda req: httpx.Response(403, json=body)))
    with pytest.raises(ContextureError) as exc:
        await om.request(user_context(), "PUT", "/services/databaseServices", json_body={})
    assert exc.value.code == "auth.om_forbidden"
    assert exc.value.status_code == 403
    assert "not allowed" in exc.value.message


async def test_not_found_is_none_when_allowed_otherwise_error() -> None:
    om, _ = client(httpx.MockTransport(lambda req: httpx.Response(404, json={"message": "x"})))
    assert await om.request(user_context(), "GET", "/x", allow_404=True) is None
    with pytest.raises(ContextureError) as exc:
        await om.request(user_context(), "GET", "/x")
    assert exc.value.code == "upstream.not_found"
    assert exc.value.status_code == 404


async def test_client_error_keeps_om_message() -> None:
    body = {"code": 400, "message": "Failed to deploy Ingestion Pipeline"}
    om, _ = client(httpx.MockTransport(lambda req: httpx.Response(400, json=body)))
    with pytest.raises(ContextureError) as exc:
        await om.request(user_context(), "POST", "/services/ingestionPipelines/deploy/1")
    assert exc.value.code == "upstream.rejected"
    assert exc.value.status_code == 400
    assert exc.value.message == "Failed to deploy Ingestion Pipeline"


async def test_any_password_in_response_is_masked() -> None:
    payload = {
        "connection": {"config": {"authType": {"password": "plain"}, "password": "plain2"}},
        "items": [{"password": "p3"}],
    }
    om, _ = client(httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))
    got = await om.request(user_context(), "GET", "/services/databaseServices/name/x")
    assert "plain" not in json.dumps(got) and "p3" not in json.dumps(got)
    assert got["connection"]["config"]["authType"]["password"] == MASK


async def test_json_patch_uses_patch_content_type() -> None:
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["ct"] = req.headers["content-type"]
        seen["body"] = req.content.decode()
        return httpx.Response(200, json={})

    om, _ = client(httpx.MockTransport(handler))
    await om.request(user_context(), "PATCH", "/tables/1", patch=[{"op": "add", "path": "/a", "value": 1}])
    assert seen["ct"] == "application/json-patch+json"
    assert json.loads(seen["body"]) == [{"op": "add", "path": "/a", "value": 1}]
