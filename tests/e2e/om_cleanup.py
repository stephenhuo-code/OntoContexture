"""e2e 清理：以 admin1（OM 管理员）删除指定数据源及其下属实体；不存在时忽略。"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from support.cluster import exchange, port_forward, user_token  # noqa: E402

token = exchange(user_token("admin1", "admin1"), "contexture-openmetadata")
with port_forward("svc/openmetadata", 8585) as url:
    for name in sys.argv[1:]:
        r = httpx.delete(
            f"{url}/api/v1/services/databaseServices/name/{name}",
            params={"hardDelete": "true", "recursive": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        assert r.status_code in (200, 404), r.text
