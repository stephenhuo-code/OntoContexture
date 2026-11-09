"""006 集群集成测试共用：以 admin1 的委托令牌经真实 OM 调用搜索与摘要（-m cluster）。

前置：make up、make seed、make dev-metadata（开发态测试元数据，testdata/mockfactory/om_import）。
断言依据导入工具的 fixture 与 OM 实际返回，不依据原型数值。
"""

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "testdata"))
from support.cluster import exchange, port_forward, user_token

from contexture_bff.adapters.om_assets import AssetReader
from contexture_bff.adapters.om_client import OmClient
from contexture_bff.adapters.om_search import SearchService
from contexture_core.auth import RequestContext
from mockfactory.om_import import fixture as fx

MARKER = fx.MARKER_FQN
FIXTURE = fx.build({t: {"id": "x", "type": "team"} for t in fx.TEAM_NAMES})
TABLES = [e for e in FIXTURE if e.kind == "table"]
CTX = RequestContext(
    tenant_id="local", user_id="it", agent_id="bff", roles=("admin",), token_id="it", token="x"
)


class AdminExchanger:
    def __init__(self) -> None:
        self.token, self.at = "", 0.0

    async def exchange(self, subject_token: str, audience: str) -> str:
        if time.monotonic() - self.at > 240:
            self.token, self.at = (
                exchange(user_token("admin1", "admin1"), audience),
                time.monotonic(),
            )
        return self.token


@contextmanager
def om() -> Iterator[tuple[SearchService, AssetReader, OmClient]]:
    with port_forward("svc/openmetadata", 8585) as url:
        client = OmClient(om_url=url, exchanger=AdminExchanger())
        yield SearchService(client), AssetReader(client), client


def dev_filter(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """只看开发态测试资产：分类标签维度选中开发态标识（取值为 OM 归一化后的小写桶键）。"""
    filters: dict[str, Any] = {"tag": {"values": [MARKER.lower()]}}
    return {**filters, **(extra or {})}
