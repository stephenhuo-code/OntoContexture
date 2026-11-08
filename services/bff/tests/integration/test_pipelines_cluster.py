"""US2 集成（真实 OM / Airflow，-m cluster）：暂停 / 恢复同步到 Airflow DAG；立即运行产生新的 PipelineStatus；最近日志可读。
以 engineer1 的委托令牌操作（验证 R12 权限含 toggleIngestion 所需的 EditIngestionPipelineStatus）。"""

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
NAME = "ctx005-it-runs"


class UserExchanger:
    def __init__(self, user: str) -> None:
        self.user, self.token, self.at = user, "", 0.0

    async def exchange(self, subject_token: str, audience: str) -> str:
        if time.monotonic() - self.at > 240:
            self.token, self.at = exchange(user_token(self.user, self.user), audience), time.monotonic()
        return self.token


_PAUSED_PY = """
import json, os, sys, urllib.request
base = "http://localhost:8080"
req = urllib.request.Request(base + "/auth/token", method="POST",
    data=json.dumps({"username": "openmetadata", "password": os.environ["OM_AIRFLOW_PASSWORD"]}).encode(),
    headers={"Content-Type": "application/json"})
token = json.load(urllib.request.urlopen(req))["access_token"]
dag = urllib.request.Request(base + "/api/v2/dags/" + sys.argv[1], headers={"Authorization": "Bearer " + token})
print(json.load(urllib.request.urlopen(dag))["is_paused"])
"""


def _dag_paused(dag_id: str) -> bool:
    """测试经 Airflow 自身 REST 接口核对 DAG 暂停状态（仅测试；BFF 不直连 Airflow）。"""
    out = subprocess.run(
        ["kubectl", "-n", "contexture", "exec", "deploy/airflow-api-server", "-c", "api-server", "--",
         "python", "-c", _PAUSED_PY, dag_id],
        check=True, capture_output=True, text=True,
    ).stdout.strip().splitlines()[-1]
    return out == "True"


def _pw() -> str:
    raw = subprocess.run(
        ["kubectl", "-n", "mock-sources", "get", "secret", "mock-readonly", "-o", "jsonpath={.data.mes-meta-ro}"],
        check=True, capture_output=True, text=True,
    ).stdout
    return base64.b64decode(raw).decode()


async def _run(url: str) -> None:
    eng = SourcesService(OmClient(om_url=url, exchanger=UserExchanger("engineer1")), poll_interval=2)
    adm = SourcesService(OmClient(om_url=url, exchanger=UserExchanger("admin1")), poll_interval=2)
    ctx = RequestContext(tenant_id="local", user_id="it", agent_id="bff", roles=("ai-engineer",), token_id="it", token="x")

    async def cleanup() -> None:
        await adm.om.request(ctx, "DELETE", f"/services/databaseServices/name/{NAME}",
                             params={"hardDelete": "true", "recursive": "true"}, allow_404=True)

    await cleanup()
    try:
        await eng.create_source(ctx, {
            "name": NAME, "displayName": NAME, "serviceType": "Mysql",
            "connection": {"hostPort": "mock-mes.mock-sources.svc:3306", "username": "mes_meta_ro",
                           "password": _pw(), "database": "mes", "tls": False},
            "scope": {"includeViews": True}, "metadataSchedule": {"cron": "0 2 * * *"}, "createLineageTask": False,
        })
        dag = (await eng.get_source(ctx, NAME))["pipelines"][0]["name"]
        view = await eng.set_schedule(ctx, NAME, "metadata", enabled=False)
        assert view["scheduleEnabled"] is False
        assert _dag_paused(dag) is True
        view = await eng.set_schedule(ctx, NAME, "metadata", enabled=True)
        assert view["scheduleEnabled"] is True
        assert _dag_paused(dag) is False
        await eng.trigger(ctx, NAME, "metadata")
        run = await eng.wait_for_run(ctx, NAME, "metadata", timeout=300)
        assert run["pipelineState"] == "success"
        runs = await eng.list_runs(ctx, NAME, "metadata")
        assert runs[0]["runId"] == run["runId"]
        logs = await eng.last_logs(ctx, NAME, "metadata")
        assert logs["logs"] and _pw() not in logs["logs"]
    finally:
        await cleanup()


def test_schedule_toggle_trigger_runs_and_logs() -> None:
    with port_forward("svc/openmetadata", 8585) as url:
        asyncio.run(_run(url))
