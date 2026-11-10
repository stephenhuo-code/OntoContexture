"""US1 集成（真实 OM，-m cluster）：表与列的摘要与 OM 实体逐项一致（FR-012、FR-014）。"""

import asyncio
from urllib.parse import quote

import pytest
from cluster_assets import CTX, TABLES, om

pytestmark = pytest.mark.cluster


def test_table_and_column_summary_match_om_entity() -> None:
    t = next(e for e in TABLES if e.body["name"] == "employee")

    async def run() -> None:
        with om() as (_, reader, client):
            s = await reader.summary(CTX, "table", t.fqn)
            raw = await client.request(
                CTX,
                "GET",
                f"/tables/name/{quote(t.fqn, safe='')}",
                params={"fields": "columns,tags,owners,domains,tableConstraints"},
            )
            assert s["ref"]["id"] == raw["id"]
            assert [c["name"] for c in s["columns"]] == [c["name"] for c in raw["columns"]]
            assert s["governance"]["origin"] == "devTest"
            tags = {x["tagFQN"] for x in raw.get("tags") or []}
            assert (
                (s["governance"]["tier"] in tags)
                if s["governance"]["tier"]
                else not any(x.startswith("Tier.") for x in tags)
            )
            levels = {c["name"]: c["dataLevel"] for c in s["columns"]}
            assert "数据级别.三级" in levels.values()
            pk = t.body["tableConstraints"][0]["columns"][0]
            assert next(c for c in s["columns"] if c["name"] == pk)["constraint"] == "PRIMARY_KEY"
            col = await reader.summary(CTX, "tableColumn", f"{t.fqn}.{pk}")
            assert col["column"]["name"] == pk and col["parentTable"]["fqn"] == t.fqn

    asyncio.run(run())
