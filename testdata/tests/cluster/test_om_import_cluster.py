"""本地集群（make up、make seed 之后）：开发态元数据导入写入真实 OM（SC-008、FR-016、FR-017）。

- 连续导入两次，第二次新建为 0，测试资产数量不变；
- 005 服务 mock-mes（如果存在）的 version 与 updatedAt 不变；
- 导入后立即能按表名搜到；撤除后搜不到；再次导入成功（PUT 会恢复已软删除的实体）；
- 观察「写入后短暂搜不到」：记录从写入完成到能搜到的耗时（spec 边界情况）。

本测试会撤除并重建开发态测试资产，结束时保持「已导入」状态。
"""

import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
from support.cluster import env, port_forward, trusted_ca

from mockfactory.om_import import fixture as fx
from mockfactory.om_import.writer import OmWriter, urllib_transport

pytestmark = pytest.mark.cluster
TABLE_COUNT = sum(1 for e in fx.build({t: {} for t in fx.TEAM_NAMES}) if e.kind == "table")


def _provisioner_token() -> str:
    e = env()
    resp = httpx.post(
        f"{e['KEYCLOAK_URL']}/realms/{e['KEYCLOAK_REALM']}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": e["KEYCLOAK_PROVISIONER_CLIENT_ID"],
            "client_secret": e["KEYCLOAK_PROVISIONER_CLIENT_SECRET"],
        },
        verify=trusted_ca(),
        timeout=10,
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


@pytest.fixture(scope="module")
def om() -> Iterator[tuple[OmWriter, httpx.Client]]:
    token = _provisioner_token()
    with (
        port_forward("svc/openmetadata", 8585) as url,
        httpx.Client(
            base_url=f"{url}/api/v1", headers={"Authorization": f"Bearer {token}"}, timeout=30
        ) as http,
    ):
        yield OmWriter(urllib_transport(url, token)), http


def _search_tables(http: httpx.Client) -> list[dict[str, Any]]:
    resp = http.get(
        "/search/query",
        params={
            "q": "*",
            "index": "table",
            "size": 100,
            "deleted": "false",
            "query_filter": json.dumps({"query": {"term": {"tags.tagFQN": fx.MARKER_FQN}}}),
        },
    )
    resp.raise_for_status()
    return [h["_source"] for h in resp.json()["hits"]["hits"]]


def _mock_mes(http: httpx.Client) -> tuple[Any, Any] | None:
    resp = http.get("/services/databaseServices/name/mock-mes")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    body = resp.json()
    return body["version"], body["updatedAt"]


def test_import_is_idempotent_searchable_and_removable(om: tuple[OmWriter, httpx.Client]) -> None:
    writer, http = om
    before_005 = _mock_mes(http)

    writer.import_all()
    second = writer.import_all()
    assert second.created == 0
    assert second.updated == 0
    assert len(_search_tables(http)) == TABLE_COUNT

    writer.remove()
    assert _search_tables(http) == []

    again = writer.import_all()
    assert again.created > 0
    started = time.monotonic()
    first_visible = None
    for _ in range(30):
        if len(_search_tables(http)) == TABLE_COUNT:
            first_visible = time.monotonic() - started
            break
        time.sleep(1)
    assert first_visible is not None, "导入后 30 秒内仍未全部搜到"
    print(f"\n[006 观察] 导入完成到全部 {TABLE_COUNT} 张表可搜到：{first_visible:.1f}s")

    assert _mock_mes(http) == before_005
