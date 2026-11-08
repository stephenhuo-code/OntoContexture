"""US3 集成（真实 OM，-m cluster）：采集 MES 后逐层读取，层级与数量等于 OM 实体与 003 金标准；MySQL 为 default → mes → 表。"""

import asyncio
import base64
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests"))
from support.cluster import exchange, port_forward, user_token  # noqa: E402

from contexture_bff.adapters.om_client import OmClient  # noqa: E402
from contexture_bff.adapters.om_sources import SourcesService  # noqa: E402
from contexture_core.auth import RequestContext  # noqa: E402

pytestmark = pytest.mark.cluster
NAME = "ctx005-it-catalog"


class AdminExchanger:
    def __init__(self) -> None:
        self.token, self.at = "", 0.0

    async def exchange(self, subject_token: str, audience: str) -> str:
        if time.monotonic() - self.at > 240:
            self.token, self.at = exchange(user_token("admin1", "admin1"), audience), time.monotonic()
        return self.token


async def _run(url: str) -> None:
    svc = SourcesService(OmClient(om_url=url, exchanger=AdminExchanger()), poll_interval=2)
    ctx = RequestContext(tenant_id="local", user_id="it", agent_id="bff", roles=("admin",), token_id="it", token="x")
    pw = base64.b64decode(subprocess.run(
        ["kubectl", "-n", "mock-sources", "get", "secret", "mock-readonly", "-o", "jsonpath={.data.mes-meta-ro}"],
        check=True, capture_output=True, text=True).stdout).decode()

    async def cleanup() -> None:
        await svc.om.request(ctx, "DELETE", f"/services/databaseServices/name/{NAME}",
                             params={"hardDelete": "true", "recursive": "true"}, allow_404=True)

    await cleanup()
    try:
        await svc.create_source(ctx, {
            "name": NAME, "displayName": NAME, "serviceType": "Mysql",
            "connection": {"hostPort": "mock-mes.mock-sources.svc:3306", "username": "mes_meta_ro",
                           "password": pw, "database": "mes", "tls": False},
            "scope": {"includeViews": True}, "metadataSchedule": {"cron": None}, "createLineageTask": False,
        })
        await svc.trigger(ctx, NAME, "metadata")
        assert (await svc.wait_for_run(ctx, NAME, "metadata", timeout=300))["pipelineState"] == "success"
        root = await svc.get_catalog_entity(ctx, "databaseService", NAME)
        assert [c["fullyQualifiedName"] for c in root["children"]] == [f"{NAME}.default"]
        db = await svc.get_catalog_entity(ctx, "database", f"{NAME}.default")
        assert [(c["name"], c["childCount"]) for c in db["children"]] == [("mes", 13)]
        schema = await svc.get_catalog_entity(ctx, "databaseSchema", f"{NAME}.default.mes")
        assert len(schema["children"]) == 13
        assert sum(c["childCount"] for c in schema["children"]) == 79
        first = schema["children"][0]["fullyQualifiedName"]
        table = await svc.get_catalog_entity(ctx, "table", first)
        assert table["table"]["columns"]
        assert any(c["constraint"] == "PRIMARY_KEY" for c in table["table"]["columns"]) or table["table"]["constraints"]
    finally:
        await cleanup()


def test_catalog_levels_match_om() -> None:
    with port_forward("svc/openmetadata", 8585) as url:
        asyncio.run(_run(url))
