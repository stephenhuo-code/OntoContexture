import socket
import threading
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
import uvicorn
from mcp.server.mcpserver import MCPServer
from opentelemetry import trace
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

from contexture_core.auth import RequestContext
from contexture_core.errors import InvalidToken, UpstreamUnavailable
from contexture_core.mcp import McpClient, TokenExchanger

TOKEN_URL = "https://sso.test/realms/digital-workforce/protocol/openid-connect/token"


class Rows(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


def build_server() -> MCPServer:
    server = MCPServer("test-toolbox")

    @server.tool()
    def list_objects(type_key: str, limit: int = 20) -> Rows:
        data = [[f"CNC-{i:02d}", "Mazak"] for i in range(1, 11)]
        return Rows(columns=["code", "model"], rows=data[:limit], truncated=len(data) > limit)

    @server.tool()
    def list_raw(type_key: str) -> str:
        """模拟 Toolbox：以 JSON 文本返回对象数组。"""
        return '[{"code": "CNC-01", "model": "Mazak"}, {"code": "CNC-02", "model": "DMG"}]'

    @server.tool()
    def broken(type_key: str) -> str:
        raise RuntimeError("tool failed")

    return server


class HeaderRecorder:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.headers: list[dict[str, str]] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            self.headers.append({k.decode(): v.decode() for k, v in scope["headers"]})
        await self.app(scope, receive, send)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def mcp_server() -> Iterator[tuple[str, HeaderRecorder]]:
    recorder = HeaderRecorder(build_server().streamable_http_app())
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(recorder, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp", recorder
    server.should_exit = True
    thread.join(timeout=5)


class FakeKeycloak:
    def __init__(self, status: int = 200) -> None:
        self.requests: list[dict[str, list[str]]] = []
        self.status = status

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url) == TOKEN_URL
            form = parse_qs(request.content.decode())
            self.requests.append(form)
            if self.status != 200:
                return httpx.Response(self.status, json={"error": "invalid_request"})
            n = len(self.requests)
            return httpx.Response(
                200,
                json={"access_token": f"exchanged-{n}", "expires_in": 300, "token_type": "Bearer"},
            )

        return httpx.MockTransport(handler)


def make_exchanger(kc: FakeKeycloak) -> TokenExchanger:
    return TokenExchanger(
        token_url=TOKEN_URL,
        client_id="contexture-bff",
        client_secret="bff-secret",
        http=httpx.AsyncClient(transport=kc.transport()),
    )


def ctx(token: str = "user-token") -> RequestContext:
    return RequestContext(
        tenant_id="local",
        user_id="user-1-id",
        agent_id="contexture-bff",
        roles=("business-user",),
        token_id="jti-1",
        token=token,
    )


async def test_exchange_request_shape() -> None:
    kc = FakeKeycloak()
    token = await make_exchanger(kc).exchange("user-token", "contexture-ai-gateway")
    assert token == "exchanged-1"
    form = kc.requests[0]
    assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:token-exchange"]
    assert form["audience"] == ["contexture-ai-gateway"]
    assert form["subject_token"] == ["user-token"]
    assert form["subject_token_type"] == ["urn:ietf:params:oauth:token-type:access_token"]
    assert form["client_id"] == ["contexture-bff"]
    assert form["client_secret"] == ["bff-secret"]


async def test_exchange_cached_per_subject_and_audience() -> None:
    kc = FakeKeycloak()
    ex = make_exchanger(kc)
    a = await ex.exchange("user-token", "contexture-ai-gateway")
    b = await ex.exchange("user-token", "contexture-ai-gateway")
    c = await ex.exchange("other-user", "contexture-ai-gateway")
    d = await ex.exchange("user-token", "other-audience")
    assert a == b
    assert len({a, c, d}) == 3
    assert len(kc.requests) == 3


async def test_exchange_refreshes_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    kc = FakeKeycloak()
    ex = make_exchanger(kc)
    now = [1000.0]
    monkeypatch.setattr("contexture_core.mcp.time.monotonic", lambda: now[0])
    await ex.exchange("user-token", "aud")
    now[0] += 300  # 超过 expires_in 减去提前量
    await ex.exchange("user-token", "aud")
    assert len(kc.requests) == 2


async def test_exchange_rejected_is_invalid_token() -> None:
    with pytest.raises(InvalidToken):
        await make_exchanger(FakeKeycloak(status=400)).exchange("bad", "aud")


async def test_exchange_server_error_is_upstream_unavailable() -> None:
    with pytest.raises(UpstreamUnavailable):
        await make_exchanger(FakeKeycloak(status=503)).exchange("t", "aud")


async def test_list_objects_sends_bearer_and_traceparent(
    mcp_server: tuple[str, HeaderRecorder],
) -> None:
    url, recorder = mcp_server
    recorder.headers.clear()
    client = McpClient(url=url, exchanger=make_exchanger(FakeKeycloak()), audience="aud")
    with trace.get_tracer("test").start_as_current_span("parent") as parent:
        result = await client.list_objects(ctx(), type_key="equipment", limit=3)
    assert result.columns == ["code", "model"]
    assert len(result.rows) == 3
    assert result.truncated is True
    assert recorder.headers
    trace_id = format(parent.get_span_context().trace_id, "032x")
    for headers in recorder.headers:
        assert headers["authorization"] == "Bearer exchanged-1"
        assert headers["traceparent"].split("-")[1] == trace_id


async def test_text_json_rows_are_converted(mcp_server: tuple[str, HeaderRecorder]) -> None:
    url, _ = mcp_server
    client = McpClient(url=url, exchanger=make_exchanger(FakeKeycloak()), audience="aud")
    result = await client.call_rows(ctx(), "list_raw", {"type_key": "equipment"})
    assert result.columns == ["code", "model"]
    assert result.rows == [["CNC-01", "Mazak"], ["CNC-02", "DMG"]]
    assert result.truncated is False


@pytest.mark.parametrize("limit", [0, 101])
async def test_limit_out_of_range_fails_on_client(limit: int) -> None:
    kc = FakeKeycloak()
    client = McpClient(url="http://unused.test/mcp", exchanger=make_exchanger(kc), audience="aud")
    with pytest.raises(ValueError, match="limit"):
        await client.list_objects(ctx(), type_key="equipment", limit=limit)
    assert kc.requests == []


async def test_tool_error_is_upstream_unavailable(mcp_server: tuple[str, HeaderRecorder]) -> None:
    url, _ = mcp_server
    client = McpClient(url=url, exchanger=make_exchanger(FakeKeycloak()), audience="aud")
    with pytest.raises(UpstreamUnavailable):
        await client.call_rows(ctx(), "broken", {"type_key": "x"})


async def test_unreachable_server_is_upstream_unavailable() -> None:
    client = McpClient(
        url=f"http://127.0.0.1:{free_port()}/mcp",
        exchanger=make_exchanger(FakeKeycloak()),
        audience="aud",
    )
    with pytest.raises(UpstreamUnavailable):
        await client.list_objects(ctx(), type_key="equipment")
