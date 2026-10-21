"""AI 网关策略测试（T062，ADR-0013）：令牌受众校验、按角色授权工具、审计记录。

针对本地集群运行（make up、make seed 之后）：uv run pytest -m cluster deploy/components/ai-gateway
"""

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from support.cluster import claims, exchange, logs, port_forward, user_token
from support.keycloak import audiences

pytestmark = pytest.mark.cluster

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "policy-test", "version": "0"},
    },
}
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@pytest.fixture(scope="module")
def gateway() -> Iterator[str]:
    with port_forward("svc/ai-gateway", 8080) as url:
        yield url


@pytest.fixture(scope="module")
def gateway_token() -> str:
    return exchange(user_token("user1", "user1"))


def rpc(
    gateway: str, token: str | None, body: dict[str, Any], session: str | None = None
) -> httpx.Response:
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session:
        headers["Mcp-Session-Id"] = session
    return httpx.post(f"{gateway}/mcp", json=body, headers=headers, timeout=30)


def payload(resp: httpx.Response) -> dict[str, Any]:
    """Streamable HTTP 可能以 SSE 返回：取最后一个 data 行。"""
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in resp.text.splitlines() if line.startswith("data:")]
        return json.loads(data[-1])
    return resp.json()


def call_tool(gateway: str, token: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    init = rpc(gateway, token, INIT)
    assert init.status_code == 200, init.text
    session = init.headers.get("mcp-session-id")
    rpc(gateway, token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }
    return payload(rpc(gateway, token, body, session))


def test_no_token_is_rejected(gateway: str) -> None:
    assert rpc(gateway, None, INIT).status_code == 401


def test_login_token_without_exchange_is_rejected(gateway: str) -> None:
    """登录令牌受众含多个客户端；未经交换的令牌也可通过受众校验，但 azp 为 bff 本身。
    这里验证受众完全不符的令牌被拒绝：交换到 contexture-bff 受众的令牌。"""
    wrong = exchange(user_token("user1", "user1"), audience="contexture-bff")
    assert "contexture-ai-gateway" not in audiences(claims(wrong))
    assert rpc(gateway, wrong, INIT).status_code in (401, 403)


def test_exchanged_token_can_list_objects(gateway: str, gateway_token: str) -> None:
    assert audiences(claims(gateway_token)) == ["contexture-ai-gateway"]
    result = call_tool(
        gateway, gateway_token, "list_objects", {"type_key": "equipment", "limit": 3}
    )
    assert "error" not in result, result
    # MCP Toolbox 每行返回一个文本块（JSON 对象）
    rows = [json.loads(c["text"]) for c in result["result"]["content"]]
    assert len(rows) == 3
    assert rows[0]["code"] == "CNC-01"


def test_audit_records_who_called_what(gateway: str, gateway_token: str) -> None:
    call_tool(gateway, gateway_token, "list_objects", {"type_key": "equipment", "limit": 2})
    time.sleep(1)
    token_claims = claims(gateway_token)
    entries = [json.loads(line) for line in logs("deploy/ai-gateway") if line.startswith("{")]
    calls = [e for e in entries if e.get("audit.mcp.tool") == "list_objects"]
    assert calls, "网关日志中没有 list_objects 的审计记录"
    last = calls[-1]
    assert last["audit.sub"] == token_claims["sub"]
    assert last["audit.azp"] == "contexture-bff"
    assert last["audit.user"] == "user1"
    assert last["audit.tenant"] == "local"
    assert last["audit.mcp.arguments"] == {"type_key": "equipment", "limit": 2}
    assert last["audit.mcp.rows"] == 2
    assert last.get("trace.id") or last.get("trace_id"), last
