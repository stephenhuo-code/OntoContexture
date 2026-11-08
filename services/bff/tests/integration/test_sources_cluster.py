"""US1 集成（真实 OM / Airflow / 003 模拟库，-m cluster）：经 SourcesService 接入 MES、QMS、Doris 并首采，
表数与字段数等于 003 金标准（MES 13/79、QMS 7/53、Doris 8/66），Doris 键列为 PRIMARY_KEY。"""

import asyncio
import base64
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests"))
from support.cluster import exchange, port_forward, user_token  # noqa: E402

from contexture_bff.adapters.om_client import OmClient  # noqa: E402
from contexture_bff.adapters.om_sources import SourcesService  # noqa: E402
from contexture_core.auth import RequestContext  # noqa: E402

pytestmark = pytest.mark.cluster

GOLD = {"ctx005-it-mes": (13, 79), "ctx005-it-qms": (7, 53), "ctx005-it-dw": (8, 66)}


def _secret(ns: str, name: str, key: str) -> str:
    out = subprocess.run(
        ["kubectl", "-n", ns, "get", "secret", name, "-o", f"jsonpath={{.data.{key}}}"],
        check=True, capture_output=True, text=True,
    ).stdout
    return base64.b64decode(out).decode()


class AdminExchanger:
    """以 admin1 登录并交换为 OM 受众；令牌 4 分钟后重新获取（Keycloak 访问令牌有效期 5 分钟）。"""

    def __init__(self) -> None:
        self.token = ""
        self.at = 0.0

    async def exchange(self, subject_token: str, audience: str) -> str:
        if time.monotonic() - self.at > 240:
            self.token = exchange(user_token("admin1", "admin1"), audience)
            self.at = time.monotonic()
        return self.token


def _sources() -> list[dict[str, Any]]:
    def item(name: str, stype: str, host: str, user: str, pw: str, db: str, schema: str | None = None) -> dict[str, Any]:
        scope: dict[str, Any] = {"includeViews": True}
        if schema:
            scope["schemaFilterPattern"] = {"includes": [schema], "excludes": []}
        return {
            "name": name, "displayName": name, "serviceType": stype,
            "connection": {"hostPort": host, "username": user, "password": pw, "database": db, "tls": False},
            "scope": scope, "metadataSchedule": {"cron": None}, "createLineageTask": False,
        }
    return [
        item("ctx005-it-mes", "Mysql", "mock-mes.mock-sources.svc:3306", "mes_meta_ro",
             _secret("mock-sources", "mock-readonly", "mes-meta-ro"), "mes"),
        item("ctx005-it-qms", "Postgres", "mock-qms-rw.mock-sources.svc:5432", "qms_meta_ro",
             # OM 2.0.3 的 PostgreSQL 采集默认包含 information_schema（原生无默认排除），按原型以 Schema 过滤限定 public
             _secret("mock-sources", "mock-readonly", "qms-meta-ro"), "qms", "^public$"),
        item("ctx005-it-dw", "Doris", "doris-fe-service.contexture.svc:9030", "mock_dw_reader",
             _secret("mock-sources", "mock-dw-reader", "password"), "mock_dw"),
    ]


async def _run(om_url: str) -> list[dict[str, Any]]:
    svc = SourcesService(OmClient(om_url=om_url, exchanger=AdminExchanger()), poll_interval=2)
    ctx = RequestContext(tenant_id="local", user_id="engineer1", agent_id="contexture-bff",
                         roles=("ai-engineer",), token_id="it", token="unused")
    async def cleanup() -> None:
        for name in GOLD:
            await svc.om.request(ctx, "DELETE", f"/services/databaseServices/name/{name}",
                                 params={"hardDelete": "true", "recursive": "true"}, allow_404=True)

    await cleanup()  # 上次中断可能留下实体
    try:
        for body in _sources():
            await svc.create_source(ctx, body)
            await svc.trigger(ctx, body["name"], "metadata")
        for name in GOLD:
            await svc.wait_for_run(ctx, name, "metadata", timeout=600)
        return [await svc.get_source(ctx, n) for n in GOLD]
    finally:
        await cleanup()


def test_three_mock_sources_ingested_to_gold_counts() -> None:
    # 清理需要 admin（OM 管理员）：engineer1 的权限不含删除数据源（research R12）
    with port_forward("svc/openmetadata", 8585) as url:
        details = asyncio.run(_run(url))
    got = {d["name"]: (d["tableCount"], d["columnCount"]) for d in details}
    assert got == GOLD
    for d in details:
        assert d["connection"]["password"] == "*********"
        run = d["pipelines"][0]["lastRun"]
        assert run["pipelineState"] == "success"
