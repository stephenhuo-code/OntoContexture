"""e2e 核对：以 admin1 读取 OM 血缘接口，输出各视图的上游表与字段映射（JSON），供端到端对照 viewlab
标准答案。"""

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.cluster import exchange, port_forward, user_token

schema_fqn, *views = sys.argv[1:]
token = exchange(user_token("admin1", "admin1"), "contexture-openmetadata")
out: dict[str, dict[str, object]] = {}
with port_forward("svc/openmetadata", 8585) as url:
    for view in views:
        g = (
            httpx.get(
                f"{url}/api/v1/lineage/table/name/{schema_fqn}.{view}",
                params={"upstreamDepth": 1, "downstreamDepth": 0},
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
            .raise_for_status()
            .json()
        )
        names = {n["id"]: n["fullyQualifiedName"] for n in g.get("nodes") or []}
        tables: list[str] = []
        columns: dict[str, list[str]] = {}
        for e in g.get("upstreamEdges") or []:
            tables.append(names[e["fromEntity"]].rsplit(".", 1)[-1])
            for cl in (e.get("lineageDetails") or {}).get("columnsLineage") or []:
                to = cl["toColumn"].rsplit(".", 1)[-1]
                columns.setdefault(to, []).extend(
                    ".".join(f.rsplit(".", 2)[-2:]) for f in cl.get("fromColumns") or []
                )
        out[view] = {
            "tables": sorted(tables),
            "columns": {k: sorted(v) for k, v in sorted(columns.items())},
        }
print(json.dumps(out, ensure_ascii=False, sort_keys=True))
