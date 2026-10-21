"""make seed：端到端骨架的示例数据（T068）。幂等，可重复执行。

- OpenMetadata：领域包术语库 quality；对象“设备”（Equipment）及 5 个属性术语，以 hasProperty 关联，
  共用字段写在术语的自定义属性中，属性贴“数据级别”标签；没有审核人，创建即为已审批（ADR-0008）。
- Doris：本体实例库 ctx_<tenant_id> 中建 equipment 表并写入 10 行示例数据（第一列为业务主键）。
- 取出 OM 的 ingestion-bot 令牌，写入 bff 的 Secret（bff 经它读取已审批的对象定义）。

用法：python -m tools.seed（由 make seed 调用；经 kubectl port-forward 访问集群内服务）
"""

import base64
import contextlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pymysql

from tools.om_config import provisioner_token

NS = "contexture"
DATA_LEVEL = "数据级别"
LEVELS = {"一级": "公开或内部一般数据", "二级": "内部敏感数据", "三级": "重要数据"}

OBJECT = {"name": "Equipment", "displayName": "设备", "description": "生产设备，如数控机床"}
# (名称, 显示名, 数据类型, 必填, 作用, 数据级别)
PROPERTIES = [
    ("code", "设备编号", "string", "是", "主键", "一级"),
    ("name", "设备名称", "string", "是", "显示", "一级"),
    ("model", "型号", "string", "否", "无", "二级"),
    ("line", "所在产线", "string", "否", "无", "二级"),
    ("installed_at", "投产日期", "date", "否", "无", "三级"),
]

EQUIPMENT_ROWS = [
    (f"CNC-{i:02d}", f"{i} 号数控机床", model, line, f"2024-{(i % 12) + 1:02d}-15")
    for i, (model, line) in enumerate(
        [
            ("Mazak QTN-200", "L1"),
            ("Mazak QTN-200", "L1"),
            ("DMG CTX 310", "L1"),
            ("DMG CTX 310", "L2"),
            ("Haas ST-20", "L2"),
            ("Haas ST-20", "L2"),
            ("Okuma LB3000", "L3"),
            ("Okuma LB3000", "L3"),
            ("Mazak VCN-530", "L3"),
            ("DMG DMU 50", "L3"),
        ],
        start=1,
    )
]

DORIS_SQL = [
    """CREATE TABLE IF NOT EXISTS equipment (
  code VARCHAR(32) NOT NULL COMMENT '设备编号',
  name VARCHAR(128) NOT NULL COMMENT '设备名称',
  model VARCHAR(64) COMMENT '型号',
  line VARCHAR(16) COMMENT '所在产线',
  installed_at DATE COMMENT '投产日期'
) UNIQUE KEY(code)
DISTRIBUTED BY HASH(code) BUCKETS 1
PROPERTIES ("replication_num" = "1")""",
]


# ---------------------------------------------------------------- OpenMetadata


def _get(http: httpx.Client, path: str) -> dict[str, Any] | None:
    resp = http.get(f"/api/v1{path}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return dict(resp.json())


def _post(http: httpx.Client, path: str, body: dict[str, Any]) -> dict[str, Any]:
    resp = http.post(f"/api/v1{path}", json=body)
    if resp.is_error:
        raise RuntimeError(f"POST {path} -> {resp.status_code}: {resp.text[:500]}")
    return dict(resp.json())


def _ensure_term(http: httpx.Client, glossary: str, body: dict[str, Any]) -> dict[str, Any]:
    fqn = f"{glossary}.{body['name']}"
    term = _get(http, f"/glossaryTerms/name/{fqn}?fields=relatedTerms,extension,tags")
    return term or _post(http, "/glossaryTerms", {"glossary": glossary, **body})


def seed_om(http: httpx.Client, glossary: str = "quality") -> None:
    if _get(http, f"/classifications/name/{DATA_LEVEL}") is None:
        _post(http, "/classifications", {"name": DATA_LEVEL, "description": "数据级别（宪法 IV）"})
    for level, desc in LEVELS.items():
        if _get(http, f"/tags/name/{DATA_LEVEL}.{level}") is None:
            _post(http, "/tags", {"classification": DATA_LEVEL, "name": level, "description": desc})
    if _get(http, f"/glossaries/name/{glossary}") is None:
        _post(
            http,
            "/glossaries",
            {
                "name": glossary,
                "displayName": "质量领域包",
                "description": "质量领域包的本体（ADR-0008）",
            },
        )

    props = []
    for name, display, dtype, required, key, level in PROPERTIES:
        props.append(
            _ensure_term(
                http,
                glossary,
                {
                    "name": name,
                    "displayName": display,
                    "description": f"设备属性：{display}",
                    # 枚举型自定义属性在 OM 中以数组存值
                    "extension": {
                        "ctx_kind": ["property"],
                        "ctx_uri": f"urn:ctx:property:{glossary}:{name}",
                        "ctx_data_type": [dtype],
                        "ctx_required": [required],
                        "ctx_key": [key],
                    },
                    "tags": [{"tagFQN": f"{DATA_LEVEL}.{level}", "source": "Classification"}],
                },
            )
        )
    obj = _ensure_term(
        http,
        glossary,
        {
            **OBJECT,
            "extension": {
                "ctx_kind": ["object"],
                "ctx_uri": f"urn:ctx:object:{glossary}:{OBJECT['name']}",
            },
        },
    )

    linked = {
        r["term"]["id"]
        for r in obj.get("relatedTerms") or []
        if r.get("relationType") == "hasProperty"
    }
    ops = [
        {
            "op": "add",
            "path": "/relatedTerms/-",
            "value": {
                "relationType": "hasProperty",
                "term": {"id": p["id"], "type": "glossaryTerm"},
            },
        }
        for p in props
        if p["id"] not in linked
    ]
    if ops:
        resp = http.patch(
            f"/api/v1/glossaryTerms/{obj['id']}",
            content=json.dumps(ops),
            headers={"Content-Type": "application/json-patch+json"},
        )
        resp.raise_for_status()


def bot_token(http: httpx.Client, bot: str = "ingestion-bot") -> str:
    user = http.get(f"/api/v1/bots/name/{bot}").raise_for_status().json()["botUser"]
    auth = http.get(f"/api/v1/users/auth-mechanism/{user['id']}").raise_for_status().json()
    return str(auth["config"]["JWTToken"])


# ---------------------------------------------------------------- Doris


def wait_backends(conn: Any, timeout: float = 300) -> None:
    """等待至少一个 BE 存活（BE 重启后 FE 需数秒到数十秒重新建立心跳）。"""
    deadline = time.monotonic() + timeout
    while True:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SHOW BACKENDS")
            if any(str(b.get("Alive")).lower() == "true" for b in cur.fetchall()):
                return
        if time.monotonic() > deadline:
            raise TimeoutError("Doris BE 未就绪")
        time.sleep(5)


def seed_doris(conn: Any, database: str) -> None:
    wait_backends(conn)
    with conn.cursor() as cur:
        cur.execute(f"USE {database}")
        for sql in DORIS_SQL:
            cur.execute(sql)
        cur.executemany(
            "INSERT INTO equipment (code, name, model, line, installed_at) VALUES (%s,%s,%s,%s,%s)",
            EQUIPMENT_ROWS,
        )


# ---------------------------------------------------------------- 集群访问


def _kubectl(*args: str) -> str:
    out = subprocess.run(["kubectl", "-n", NS, *args], check=True, capture_output=True, text=True)  # noqa: S603, S607
    return out.stdout


def _secret(name: str, key: str) -> str:
    raw = _kubectl("get", "secret", name, "-o", f"jsonpath={{.data.{key}}}")
    return base64.b64decode(raw).decode()


@contextlib.contextmanager
def port_forward(target: str, port: int) -> Iterator[None]:
    proc = subprocess.Popen(  # noqa: S603
        ["kubectl", "-n", NS, "port-forward", target, f"{port}:{port}"],  # noqa: S607
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(3)
        yield
    finally:
        proc.terminate()


def main() -> int:
    tenant = os.environ.get("CTX_TENANT_ID", "local")
    with port_forward("svc/openmetadata", 8585):
        with httpx.Client(base_url="http://localhost:8585", timeout=30) as http:
            http.headers["Authorization"] = f"Bearer {provisioner_token()}"
            seed_om(http)
            token = bot_token(http)
        print("OpenMetadata：设备对象与 5 个属性（已审批）")
    patch = json.dumps({"stringData": {"ctx_om_token": token}})
    _kubectl("patch", "secret", "bff-secrets", "--type", "merge", "-p", patch)
    _kubectl("rollout", "restart", "deployment/contexture-bff")
    print("bff：已写入 OM 机器人令牌并重启")

    with port_forward("svc/doris-fe-service", 9030):
        conn = pymysql.connect(
            host="127.0.0.1",
            port=9030,
            user="root",
            password=_secret("doris-root", "password"),
            autocommit=True,
        )
        try:
            seed_doris(conn, f"ctx_{tenant}")
        finally:
            conn.close()
    print(f"Doris：ctx_{tenant}.equipment 写入 {len(EQUIPMENT_ROWS)} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
