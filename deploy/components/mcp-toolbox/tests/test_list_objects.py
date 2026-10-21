"""MCP Toolbox 的 list_objects 工具（T061、T066，契约 contracts/mcp/list_objects.yaml）。

针对本地集群的 Doris（make up、make seed 之后）：
  uv run pytest -m cluster deploy/components/mcp-toolbox
"""

import base64
import json
import subprocess
from collections.abc import Iterator
from typing import Any

import httpx
import pymysql
import pytest
from support.cluster import NS, port_forward

pytestmark = pytest.mark.cluster

HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@pytest.fixture(scope="module")
def toolbox() -> Iterator[str]:
    with port_forward("svc/mcp-toolbox", 5000) as url:
        yield url


def call(toolbox: str, args: dict[str, Any]) -> dict[str, Any]:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "list_objects", "arguments": args},
    }
    # Toolbox 只接受集群内的服务名作为 Host（--allowed-hosts）
    headers = {**HEADERS, "Host": "mcp-toolbox"}
    # 本机端口转发，不经环境中的代理
    resp = httpx.post(f"{toolbox}/mcp", json=body, headers=headers, timeout=30, trust_env=False)
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


def rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    assert not result["result"].get("isError"), result
    return [json.loads(c["text"]) for c in result["result"]["content"]]


def test_returns_equipment_rows(toolbox: str) -> None:
    data = rows(call(toolbox, {"type_key": "equipment", "limit": 20}))
    assert len(data) == 10
    assert list(data[0]) == ["code", "name", "model", "line", "installed_at"]  # 第一列为业务主键
    assert [r["code"] for r in data] == sorted(r["code"] for r in data)


def test_limit_applies(toolbox: str) -> None:
    assert len(rows(call(toolbox, {"type_key": "equipment", "limit": 3}))) == 3


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_out_of_range_rejected(toolbox: str, limit: int) -> None:
    result = call(toolbox, {"type_key": "equipment", "limit": limit})
    assert "error" in result or result["result"].get("isError"), result


def test_unknown_table_rejected(toolbox: str) -> None:
    result = call(toolbox, {"type_key": "mysql.user", "limit": 1})
    assert "error" in result or result["result"].get("isError"), result


def test_reader_account_cannot_write() -> None:
    raw = subprocess.run(
        ["kubectl", "-n", NS, "get", "secret", "doris-reader", "-o", "jsonpath={.data.password}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    with port_forward("svc/doris-fe-service", 9030) as url:
        port = int(url.rsplit(":", 1)[1])
        conn = pymysql.connect(
            host="127.0.0.1",
            port=port,
            user="ctx_reader",
            password=base64.b64decode(raw).decode(),
            database="ctx_local",
        )
        try:
            with conn.cursor() as cur, pytest.raises(pymysql.err.MySQLError):
                cur.execute("INSERT INTO equipment (code, name) VALUES ('X-1', 'x')")
        finally:
            conn.close()
