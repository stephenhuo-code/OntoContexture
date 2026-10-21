"""最终演示第 3–4 步（T065）：按一次请求的 trace_id 查到全链路 span；
AI 网关审计记录人、调用方、工具、行数。

需要本地集群（make up、make seed）：uv run pytest -m cluster tests/e2e
"""

import base64
import json
import subprocess
import time
from typing import Any

import httpx
import pytest
from support.cluster import NS, browser_session, logs, port_forward

pytestmark = pytest.mark.cluster


def _secret(name: str, key: str) -> str:
    raw = subprocess.run(
        ["kubectl", "-n", NS, "get", "secret", name, "-o", f"jsonpath={{.data.{key}}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return base64.b64decode(raw).decode()


@pytest.fixture(scope="module")
def request_trace() -> tuple[str, str]:
    """重启 bff（清空对象定义缓存），以 user1 发起一次示例查询，返回 (trace_id, 用户 ID)。"""
    subprocess.run(["kubectl", "-n", NS, "rollout", "restart", "deploy/contexture-bff"], check=True)
    subprocess.run(
        ["kubectl", "-n", NS, "rollout", "status", "deploy/contexture-bff", "--timeout=180s"],
        check=True,
        capture_output=True,
    )
    time.sleep(5)
    app = browser_session("user1", "user1")
    me = app.get("/bff/v1/me").json()
    resp = app.get("/bff/v1/object-types/equipment/objects", params={"limit": 4})
    assert resp.status_code == 200, resp.text
    return resp.json()["trace_id"], me["user_id"]


def observations(trace_id: str) -> list[dict[str, Any]]:
    auth = (_secret("langfuse-init", "public-key"), _secret("langfuse-init", "secret-key"))
    with port_forward("svc/langfuse-web", 3000) as lf:
        data: list[dict[str, Any]] = []
        for _ in range(18):  # Langfuse 异步写入，最多等 3 分钟
            resp = httpx.get(
                f"{lf}/api/public/v2/observations",
                params={"traceId": trace_id, "limit": 100, "fields": "core,basic,metadata"},
                auth=auth,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            services = {o["metadata"].get("resourceAttributes.service.name") for o in data}
            if {"contexture-gateway", "bff", "agentgateway", "mcp-toolbox"} <= services:
                break
            time.sleep(10)
        return data


def test_trace_spans_all_services(request_trace: tuple[str, str]) -> None:
    trace_id, user_id = request_trace
    obs = observations(trace_id)
    services = {o["metadata"].get("resourceAttributes.service.name") for o in obs}
    assert {"contexture-gateway", "bff", "agentgateway", "mcp-toolbox"} <= services, services
    # bff → OM（读取已审批的对象定义）
    assert any(
        o["metadata"].get("resourceAttributes.service.name") == "bff"
        and "openmetadata" in json.dumps(o["metadata"])
        for o in obs
    ), "缺少 bff → OM 的 span"
    # 每个 span 带同一个租户
    tenants = {o["metadata"].get("attributes.ctx.tenant.id") for o in obs}
    assert tenants == {"local"}, tenants
    # 人与调用方贯穿 bff 与 AI 网关
    users = {o["metadata"].get("attributes.ctx.user.id") for o in obs} - {None}
    assert users == {user_id}, users


def test_gateway_audit_for_the_request(request_trace: tuple[str, str]) -> None:
    trace_id, user_id = request_trace
    entries = [
        json.loads(line) for line in logs("deploy/ai-gateway", since="5m") if line.startswith("{")
    ]
    calls = [
        e
        for e in entries
        if e.get("audit.mcp.tool") == "list_objects" and trace_id in json.dumps(e)
    ]
    assert calls, "AI 网关没有本次请求的审计记录"
    audit = calls[-1]
    assert audit["audit.sub"] == user_id
    assert audit["audit.azp"] == "contexture-bff"
    assert audit["audit.tenant"] == "local"
    assert audit["audit.mcp.arguments"] == {"type_key": "equipment", "limit": 4}
    assert audit["audit.mcp.rows"] == 4
