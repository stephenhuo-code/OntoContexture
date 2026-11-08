"""e2e 前置：等待 OM 搜索索引中出现指定服务的视图。

视图血缘任务从搜索索引读取视图定义（research R14）。"""

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.cluster import exchange, port_forward, user_token

service, *views = sys.argv[1:]
token = exchange(user_token("admin1", "admin1"), "contexture-openmetadata")
with port_forward("svc/openmetadata", 8585) as url:
    deadline = time.monotonic() + 180
    while True:
        r = httpx.get(
            f"{url}/api/v1/search/query",
            params={"q": " OR ".join(views), "index": "table_search_index", "size": 50},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        ).raise_for_status()
        hits = r.json()["hits"]["hits"]
        found = {
            h["_source"]["name"]
            for h in hits
            if h["_source"]["fullyQualifiedName"].startswith(f"{service}.")
            and h["_source"].get("schemaDefinition")
        }
        if set(views) <= found:
            print("indexed", sorted(found))
            break
        if time.monotonic() > deadline:
            raise SystemExit(f"180 s 内搜索索引未出现视图：{sorted(set(views) - found)}")
        time.sleep(3)
