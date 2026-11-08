"""US5 集成（真实 OM，-m cluster）：viewlab 先元数据采集、再视图血缘；OM
血缘接口中每个视图的上游表与
columnsLineage 与 testdata/mockfactory/viewlab.py 标准答案完全一致、无多余边。
MySQL 受限账号（无 SHOW VIEW）：表与字段仍入库、不产生血缘边、运行结果以 OM 实际状态为准（research
R10；
PostgreSQL 无法用权限复现“视图定义不可读”，只验证有权限时的血缘）。"""

import asyncio
import base64
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "testdata"))
from support.cluster import exchange, port_forward, user_token  # noqa: E402

from contexture_bff.adapters.om_client import OmClient  # noqa: E402
from contexture_bff.adapters.om_sources import SourcesService  # noqa: E402
from contexture_core.auth import RequestContext  # noqa: E402
from mockfactory.viewlab import LINEAGE, TABLES, VIEWS  # noqa: E402

pytestmark = pytest.mark.cluster
VERBOSE = bool(os.environ.get("CTX_VERBOSE"))


class UserExchanger:
    def __init__(self, user: str) -> None:
        self.user, self.token, self.at = user, "", 0.0

    async def exchange(self, subject_token: str, audience: str) -> str:
        if time.monotonic() - self.at > 240:
            self.token = exchange(user_token(self.user, self.user), audience)
            self.at = time.monotonic()
        return self.token


def _password(key: str) -> str:
    out = subprocess.run(
        [
            "kubectl",
            "-n",
            "mock-sources",
            "get",
            "secret",
            "mock-readonly",
            "-o",
            f"jsonpath={{.data.{key}}}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return base64.b64decode(out).decode()


CASES = {
    # 名称: (连接器, 主机, 账号, 视图所在 Schema 的 FQN 后缀, Schema 过滤)
    "ctx005-it-vl-my": (
        "Mysql",
        "mock-mes.mock-sources.svc:3306",
        "viewlab_ro",
        "default.viewlab",
        None,
    ),
    "ctx005-it-vl-pg": (
        "Postgres",
        "mock-qms-rw.mock-sources.svc:5432",
        "viewlab_ro",
        "viewlab.public",
        "^public$",
    ),
    "ctx005-it-vl-noview": (
        "Mysql",
        "mock-mes.mock-sources.svc:3306",
        "viewlab_noview",
        "default.viewlab",
        None,
    ),
}


def _body(name: str) -> dict[str, Any]:
    stype, host, user, _, schema = CASES[name]
    scope: dict[str, Any] = {"includeViews": True}
    if schema:
        scope["schemaFilterPattern"] = {"includes": [schema], "excludes": []}
    return {
        "name": name,
        "displayName": name,
        "serviceType": stype,
        "connection": {
            "hostPort": host,
            "username": user,
            "password": _password(user.replace("_", "-")),
            "database": "viewlab",
            "tls": False,
        },
        "scope": scope,
        "metadataSchedule": {"cron": None},
        "createLineageTask": True,
        "lineageSchedule": {"cron": None},
    }


async def _lineage(svc: SourcesService, ctx: RequestContext, view_fqn: str) -> dict[str, Any]:
    """视图的上游：{表名: ...}、{视图字段: [表.字段]}，均取自 OM 血缘接口。"""
    g = await svc.om.request(
        ctx,
        "GET",
        f"/lineage/table/name/{view_fqn}",
        params={"upstreamDepth": 1, "downstreamDepth": 0},
    )
    names = {n["id"]: n["fullyQualifiedName"] for n in g.get("nodes") or []}
    view_id = g["entity"]["id"]
    tables: list[str] = []
    columns: dict[str, list[str]] = {}
    for e in g.get("upstreamEdges") or []:
        assert e["toEntity"] == view_id, f"多余的边：{e}"
        tables.append(names[e["fromEntity"]].rsplit(".", 1)[-1])
        for cl in (e.get("lineageDetails") or {}).get("columnsLineage") or []:
            to = cl["toColumn"].rsplit(".", 1)[-1]
            columns.setdefault(to, []).extend(
                ".".join(f.rsplit(".", 2)[-2:]) for f in cl.get("fromColumns") or []
            )
    return {"tables": sorted(tables), "columns": {k: sorted(v) for k, v in columns.items()}}


async def _run(url: str) -> dict[str, Any]:
    svc = SourcesService(
        OmClient(om_url=url, exchanger=UserExchanger("engineer1")), poll_interval=2
    )
    admin = OmClient(
        om_url=url, exchanger=UserExchanger("admin1")
    )  # 清理：数据工程角色不能删除数据源
    ctx = RequestContext(
        tenant_id="local",
        user_id="engineer1",
        agent_id="bff",
        roles=("ai-engineer",),
        token_id="it",
        token="x",
    )

    async def cleanup(name: str) -> None:
        await admin.request(
            ctx,
            "DELETE",
            f"/services/databaseServices/name/{name}",
            params={"hardDelete": "true", "recursive": "true"},
            allow_404=True,
        )

    async def run(name: str, kind: str) -> dict[str, Any]:
        await svc.trigger(ctx, name, kind)
        return await svc.wait_for_run(ctx, name, kind, timeout=300)

    observed: dict[str, Any] = {}
    for name in CASES:
        await cleanup(name)
    try:
        for name in CASES:
            await svc.create_source(ctx, _body(name))
        for name in CASES:
            meta = await run(name, "metadata")
            lin = await run(name, "lineage")
            schema_fqn = f"{name}.{CASES[name][3]}"
            schema = await svc.get_catalog_entity(ctx, "databaseSchema", schema_fqn)
            children = {c["name"]: c["childCount"] for c in schema["children"]}
            views = {
                v: await _lineage(svc, ctx, f"{schema_fqn}.{v}") for v in VIEWS if v in children
            }
            logs = (await svc.last_logs(ctx, name, "lineage"))["logs"]
            observed[name] = {
                "meta": meta,
                "lineage": lin,
                "children": children,
                "views": views,
                "logs": logs,
            }
            if VERBOSE:
                print(
                    name, meta["pipelineState"], meta["steps"], lin["pipelineState"], lin["steps"]
                )
                print(children, views)
                print(logs[-3000:])
    finally:
        for name in CASES:
            await cleanup(name)
    return observed


def test_view_lineage_matches_viewlab_gold_standard() -> None:
    with port_forward("svc/openmetadata", 8585) as url:
        observed = asyncio.run(_run(url))
    gold = {
        v: {
            "tables": sorted(x["tables"]),
            "columns": {k: sorted(c) for k, c in x["columns"].items()},
        }
        for v, x in LINEAGE.items()
    }
    for name in ("ctx005-it-vl-my", "ctx005-it-vl-pg"):
        o = observed[name]
        assert o["meta"]["pipelineState"] == "success", o["meta"]
        assert o["lineage"]["pipelineState"] == "success", o["lineage"]
        assert o["children"] == {
            **{t: len(c) for t, c in TABLES.items()},
            **{v: len(LINEAGE[v]["columns"]) for v in VIEWS},
        }
        assert o["views"] == gold, name
    # 受限账号（OM 2.0.3 实测）：元数据采集如实为 failed，失败对象为两个视图、原因为 SHOW VIEW
    # 被拒；
    # 表与字段仍入库，视图不入库；视图血缘运行成功但处理 0 条记录，不产生任何血缘边
    o = observed["ctx005-it-vl-noview"]
    assert o["meta"]["pipelineState"] == "failed", o["meta"]
    failures = [f for step in o["meta"]["steps"] for f in step.get("failures") or []]
    assert sorted(f["name"] for f in failures) == sorted(VIEWS)
    assert all("SHOW VIEW command denied" in f["error"] for f in failures)
    assert o["children"] == {t: len(c) for t, c in TABLES.items()}
    assert o["views"] == {}
    assert o["lineage"]["pipelineState"] == "success"
    assert all(step["records"] == 0 for step in o["lineage"]["steps"]), o["lineage"]
