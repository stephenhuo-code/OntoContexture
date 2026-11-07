"""005 阶段 A 闸门（T020）：在真实集群上走通 OM 原生采集链路，BFF 不参与、不连源库。

1. BFF 服务账号（contexture-bff client credentials）为 admin1、engineer1 在 OM 建档并同步团队（research R13）；
2. engineer1 的委托令牌（受众 contexture-openmetadata）：测试连接 → 保存服务与 metadata 管道 → 部署 → 触发 →
   PipelineStatus 回写 → 最近日志；读取服务时密码为掩码；
3. research R5 验证项 2、3：掩码密码更新保留原值、已有服务掩码密码测试连接；
4. 全部断言基于 003 金标准（MES 13 张表 / 79 个字段），不断言原型示例值。

需要 make up、make mock-data：uv run pytest -m cluster tests/e2e/test_om_ingestion_chain.py
"""

import base64
import json
import secrets
import string
import subprocess
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from support.cluster import env, exchange, issuer, port_forward, trusted_ca, user_token

pytestmark = pytest.mark.cluster

OM_AUDIENCE = "contexture-openmetadata"
SERVICE = "ctx005-chain-mes"
MES_HOST = "mock-mes.mock-sources.svc:3306"
PATCH = {"Content-Type": "application/json-patch+json"}


def _mock_secret(name: str, key: str) -> str:
    raw = subprocess.run(
        ["kubectl", "-n", "mock-sources", "get", "secret", name, "-o", f"jsonpath={{.data.{key}}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return base64.b64decode(raw).decode()


def _service_account_token() -> str:
    resp = httpx.post(
        f"{issuer()}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "contexture-bff",
            "client_secret": env()["CONTEXTURE_BFF_CLIENT_SECRET"],
        },
        verify=trusted_ca(),
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ensure_member(om: httpx.Client, sa: str, username: str, team: str) -> None:
    """以服务账号建档并入组（BFF 登录同步的同一做法）。"""
    user = om.get(f"/users/name/{username}", headers=_bearer(sa))
    if user.status_code == 404:
        user = om.post(
            "/users",
            headers=_bearer(sa),
            json={"name": username, "email": f"{username}@contexture.local"},
        )
    user.raise_for_status()
    uid = user.json()["id"]
    t = om.get(f"/teams/name/{team}", headers=_bearer(sa), params={"fields": "users"})
    t.raise_for_status()
    if uid not in {u["id"] for u in t.json().get("users", [])}:
        resp = om.patch(
            f"/teams/{t.json()['id']}",
            headers={**_bearer(sa), **PATCH},
            content=json.dumps([{"op": "add", "path": "/users/0", "value": {"id": uid, "type": "user"}}]),
        )
        resp.raise_for_status()


def _connection(password: str) -> dict[str, Any]:
    return {
        "config": {
            "type": "Mysql",
            "hostPort": MES_HOST,
            "username": "mes_meta_ro",
            "authType": {"password": password},
            "databaseSchema": "mes",
        }
    }


def _test_connection(om: httpx.Client, token: str, password: str, service: str | None) -> dict[str, Any]:
    request: dict[str, Any] = {
        "connection": _connection(password),
        "serviceType": "Database",
        "connectionType": "Mysql",
    }
    if service:
        request["serviceName"] = service
    name = "ctx005-chain-tc-" + secrets.token_hex(4)
    wf = om.post(
        "/automations/workflows",
        headers=_bearer(token),
        json={"name": name, "workflowType": "TEST_CONNECTION", "request": request},
    )
    wf.raise_for_status()
    wid = wf.json()["id"]
    try:
        om.post(f"/automations/workflows/trigger/{wid}", headers=_bearer(token)).raise_for_status()
        for _ in range(60):
            got = om.get(f"/automations/workflows/{wid}", headers=_bearer(token)).json()
            if got.get("status") in ("Successful", "Failed"):
                return dict(got)
            time.sleep(1)
        raise AssertionError("测试连接 60 秒未完成")
    finally:
        om.delete(f"/automations/workflows/{wid}", headers=_bearer(token), params={"hardDelete": "true"})


@pytest.fixture(scope="module")
def om() -> Iterator[httpx.Client]:
    with port_forward("svc/openmetadata", 8585) as url:
        with httpx.Client(base_url=f"{url}/api/v1", timeout=120) as client:
            yield client


@pytest.fixture(scope="module")
def tokens(om: httpx.Client) -> Iterator[dict[str, str]]:
    sa = _service_account_token()
    _ensure_member(om, sa, "admin1", "admin")
    _ensure_member(om, sa, "engineer1", "ai-engineer")
    admin1 = exchange(user_token("admin1", "admin1"), OM_AUDIENCE)
    engineer1 = exchange(user_token("engineer1", "engineer1"), OM_AUDIENCE)
    yield {"sa": sa, "admin1": admin1, "engineer1": engineer1}
    existing = om.get(f"/services/databaseServices/name/{SERVICE}", headers=_bearer(admin1))
    if existing.status_code == 200:
        om.delete(
            f"/services/databaseServices/{existing.json()['id']}",
            headers=_bearer(admin1),
            params={"hardDelete": "true", "recursive": "true"},
        ).raise_for_status()


def test_service_account_cannot_create_source_services(om: httpx.Client, tokens: dict[str, str]) -> None:
    """建档身份只能建用户、改团队成员，不能创建数据源（OM 默认 Organization 策略允许其查看，密码仍为掩码）。"""
    resp = om.put(
        "/services/databaseServices",
        headers=_bearer(tokens["sa"]),
        json={"name": "ctx005-sa-probe", "serviceType": "Mysql", "connection": _connection("x")},
    )
    assert resp.status_code == 403, resp.text


def test_native_ingestion_chain(om: httpx.Client, tokens: dict[str, str]) -> None:
    password = _mock_secret("mock-readonly", "mes-meta-ro")
    eng = tokens["engineer1"]

    started = time.monotonic()
    result = _test_connection(om, eng, password, None)
    steps = {s["name"]: s for s in result["response"]["steps"]}
    assert result["status"] == "Successful"
    assert list(steps) == ["CheckAccess", "GetSchemas", "GetTables", "GetViews", "GetQueries"]
    assert all(s["passed"] for s in steps.values() if s["mandatory"])
    assert password not in json.dumps(result)
    print(f"测试连接耗时 {time.monotonic() - started:.1f}s")

    svc = om.put(
        "/services/databaseServices",
        headers=_bearer(eng),
        json={"name": SERVICE, "serviceType": "Mysql", "connection": _connection(password)},
    )
    svc.raise_for_status()
    assert svc.json()["connection"]["config"]["authType"]["password"] == "*********"
    suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    pipe = om.post(
        "/services/ingestionPipelines",
        headers=_bearer(eng),
        json={
            "name": f"{SERVICE.replace('-', '_')}_metadata_{suffix}",
            "pipelineType": "metadata",
            "service": {"id": svc.json()["id"], "type": "databaseService"},
            "sourceConfig": {
                "config": {
                    "type": "DatabaseMetadata",
                    "includeViews": True,
                    "markDeletedTables": False,
                    "overrideMetadata": False,
                }
            },
            "airflowConfig": {"scheduleInterval": None, "pipelineTimezone": "Asia/Shanghai"},
        },
    )
    pipe.raise_for_status()
    pid, fqn = pipe.json()["id"], pipe.json()["fullyQualifiedName"]
    om.post(f"/services/ingestionPipelines/deploy/{pid}", headers=_bearer(eng)).raise_for_status()
    # Airflow 3 由 dag-processor 扫描登记新 DAG（刷新间隔 10 秒），登记前触发返回 400，按此重试
    deployed_at = time.monotonic()
    for _ in range(30):
        trig = om.post(f"/services/ingestionPipelines/trigger/{pid}", headers=_bearer(eng))
        if trig.status_code == 200:
            break
        time.sleep(2)
    trig.raise_for_status()
    print(f"部署到可触发耗时 {time.monotonic() - deployed_at:.0f}s")

    status: dict[str, Any] = {}
    run_started = time.monotonic()
    for _ in range(200):
        data = om.get(
            f"/services/ingestionPipelines/{fqn}/pipelineStatus",
            headers=_bearer(eng),
            params={"startTs": 0, "endTs": int(time.time() * 1000) + 60_000},
        ).json()["data"]
        if data and data[0]["pipelineState"] in ("success", "partialSuccess", "failed"):
            status = data[0]
            break
        time.sleep(3)
    print(f"首次采集耗时 {time.monotonic() - run_started:.0f}s")
    assert status.get("pipelineState") == "success", status
    assert {s["name"] for s in status["status"]} >= {"Mysql", "OpenMetadata"}

    tables = om.get(
        "/tables", headers=_bearer(eng), params={"service": SERVICE, "limit": 100, "fields": "columns"}
    ).json()["data"]
    assert len(tables) == 13  # 003 金标准
    assert sum(len(t["columns"]) for t in tables) == 79

    logs = om.get(f"/services/ingestionPipelines/logs/{pid}/last", headers=_bearer(eng))
    assert logs.status_code == 200
    assert password not in logs.text

    # R5 验证项 2：密码保持掩码更新服务，OM 保留原密码
    om.put(
        "/services/databaseServices",
        headers=_bearer(eng),
        json={"name": SERVICE, "serviceType": "Mysql", "connection": _connection("*********")},
    ).raise_for_status()
    # R5 验证项 3：已有服务、掩码密码测试连接仍通过
    again = _test_connection(om, eng, "*********", SERVICE)
    assert again["status"] == "Successful", again["response"]
