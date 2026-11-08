"""US4 集成（真实 OM，-m cluster）：engineer1 在五个层级写入治理属性，
重新采集（overrideMetadata=false）
与修改连接配置后属性保持不变；继承来源与 OM 返回一致。"""

import asyncio
import base64
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests"))
from support.cluster import exchange, port_forward, user_token

from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_sources import SourcesService
from contexture_core.auth import RequestContext

pytestmark = pytest.mark.cluster
NAME = "ctx005-it-governance"
DB, SCHEMA = f"{NAME}.default", f"{NAME}.default.mes"


class UserExchanger:
    def __init__(self, user: str) -> None:
        self.user, self.token, self.at = user, "", 0.0

    async def exchange(self, subject_token: str, audience: str) -> str:
        if time.monotonic() - self.at > 240:
            self.token = exchange(user_token(self.user, self.user), audience)
            self.at = time.monotonic()
        return self.token


def _password() -> str:
    out = subprocess.run(
        [
            "kubectl",
            "-n",
            "mock-sources",
            "get",
            "secret",
            "mock-readonly",
            "-o",
            "jsonpath={.data.mes-meta-ro}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return base64.b64decode(out).decode()


def _body(password: str, display: str) -> dict[str, Any]:
    return {
        "name": NAME,
        "displayName": display,
        "serviceType": "Mysql",
        "connection": {
            "hostPort": "mock-mes.mock-sources.svc:3306",
            "username": "mes_meta_ro",
            "password": password,
            "database": "mes",
            "tls": False,
        },
        "scope": {"includeViews": True},
        "metadataSchedule": {"cron": None},
        "createLineageTask": False,
    }


async def _run(url: str) -> None:
    svc = SourcesService(
        OmClient(om_url=url, exchanger=UserExchanger("engineer1")), poll_interval=2
    )
    # 清理用 admin1：按 R12，数据工程角色不能删除数据源
    admin = OmClient(om_url=url, exchanger=UserExchanger("admin1"))
    ctx = RequestContext(
        tenant_id="local",
        user_id="engineer1",
        agent_id="bff",
        roles=("ai-engineer",),
        token_id="it",
        token="x",
    )
    pw = _password()

    async def cleanup() -> None:
        await admin.request(
            ctx,
            "DELETE",
            f"/services/databaseServices/name/{NAME}",
            params={"hardDelete": "true", "recursive": "true"},
            allow_404=True,
        )

    async def ingest() -> None:
        runs = await svc.list_runs(ctx, NAME, "metadata")
        prev = runs[0]["runId"] if runs else None
        await svc.trigger(ctx, NAME, "metadata")
        run = await svc.wait_for_run(ctx, NAME, "metadata", timeout=300, after_run_id=prev)
        assert run["pipelineState"] == "success"

    await cleanup()
    try:
        await svc.create_source(ctx, _body(pw, NAME))
        await ingest()
        schema = await svc.get_catalog_entity(ctx, "databaseSchema", SCHEMA)
        table = schema["children"][0]["fullyQualifiedName"]
        column = (await svc.get_catalog_entity(ctx, "table", table))["table"]["columns"][0]["name"]
        me = await svc.om.request(ctx, "GET", "/users/name/engineer1")
        owner = {"id": me["id"], "type": "user"}

        await svc.patch_catalog_entity(
            ctx, "databaseService", NAME, {"description": "服务说明", "tier": "Tier.Tier2"}
        )
        await svc.patch_catalog_entity(
            ctx, "database", DB, {"owners": [owner], "retentionPeriod": "P30D"}
        )
        await svc.patch_catalog_entity(ctx, "databaseSchema", SCHEMA, {"displayName": "生产库"})
        await svc.patch_catalog_entity(
            ctx, "table", table, {"displayName": "织境工单", "tags": ["PII.Sensitive"]}
        )
        await svc.patch_catalog_entity(
            ctx, "table", table, {"columnName": column, "description": "织境字段说明"}
        )

        async def snapshot() -> dict[str, Any]:
            t = await svc.get_catalog_entity(ctx, "table", table)
            return {
                "service": (await svc.get_catalog_entity(ctx, "databaseService", NAME))[
                    "governance"
                ],
                "database": (await svc.get_catalog_entity(ctx, "database", DB))["governance"],
                "schema": (await svc.get_catalog_entity(ctx, "databaseSchema", SCHEMA))[
                    "governance"
                ],
                "table": t["governance"],
                "column": next(c for c in t["table"]["columns"] if c["name"] == column),
            }

        before = await snapshot()
        assert (
            before["service"]["description"] == "服务说明"
            and before["service"]["tier"] == "Tier.Tier2"
        )
        assert before["table"]["displayName"] == "织境工单" and before["table"]["tags"] == [
            "PII.Sensitive"
        ]
        assert before["column"]["description"] == "织境字段说明"
        # 继承：负责人与保留周期 库 → Schema → 表
        assert [o["id"] for o in before["table"]["owners"]] == [me["id"]]
        assert before["table"]["inheritedFrom"]["owners"] == {
            "entityType": "database",
            "fullyQualifiedName": DB,
        }
        assert before["table"]["retentionPeriod"] == "P30D"

        await ingest()  # overrideMetadata=false：重新采集不覆盖人工维护的属性
        assert await snapshot() == before
        await svc.update_source(ctx, NAME, _body(pw, "改名后的显示名称"))
        after = await snapshot()
        assert (
            after["service"]["description"] == "服务说明"
            and after["service"]["tier"] == "Tier.Tier2"
        )
        assert after["table"] == before["table"]
    finally:
        await cleanup()


def test_governance_survives_reingestion_and_config_update() -> None:
    with port_forward("svc/openmetadata", 8585) as url:
        asyncio.run(_run(url))
