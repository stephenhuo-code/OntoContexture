"""005 单元测试辅助：以内存 OM（om_fake）构造 SourcesService。"""

from typing import Any

import httpx
from om_fake import FakeOM

from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_sources import SourcesService


class FakeExchanger:
    async def exchange(self, subject_token: str, audience: str) -> str:
        assert audience == "contexture-openmetadata"
        return "om-token"


def service(om: FakeOM) -> SourcesService:
    client = OmClient(
        om_url="http://om:8585",
        exchanger=FakeExchanger(),
        http=httpx.AsyncClient(transport=om.transport()),
    )
    return SourcesService(client, poll_interval=0)


def upsert(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "mock-mes",
        "displayName": "MES 生产执行系统",
        "serviceType": "Mysql",
        "connection": {
            "hostPort": "mock-mes.mock-sources.svc:3306",
            "username": "mes_meta_ro",
            "password": "secret-pw",
            "database": "mes",
            "tls": False,
        },
        "scope": {"includeViews": True},
        "metadataSchedule": {"cron": "0 2 * * *"},
        "createLineageTask": False,
    }
    body.update(overrides)
    return body
