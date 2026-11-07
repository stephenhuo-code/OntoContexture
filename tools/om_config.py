"""把本体的共用字段与关系类型写入 OpenMetadata（T046，ADR-0008）；005 起同时写入采集管理权限与
BFF 建档服务账号（research R12、R13）。幂等：只新增缺失项。

配置：deploy/components/openmetadata/config/ontology-schema.yaml
用法：python -m tools.om_config --om-url http://localhost:8585
  令牌：.env.local 中的导入服务账号向 Keycloak 换取（OM 初始管理员），或用 OM_TOKEN 提供
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, cast

import httpx
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "deploy" / "components" / "openmetadata" / "config" / "ontology-schema.yaml"
SETTING = "glossaryTermRelationSettings"


def load_schema(path: Path = SCHEMA) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def _property_body(prop: dict[str, Any], type_ids: dict[str, str]) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": prop["name"],
        "description": prop.get("description", ""),
        "propertyType": {"id": type_ids[prop["type"]], "type": "type"},
    }
    if prop["type"] == "enum":
        body["customPropertyConfig"] = {"config": {"values": prop["values"], "multiSelect": False}}
    elif prop["type"] == "entityReference":
        body["customPropertyConfig"] = {"config": prop["entityTypes"]}
    return body


def apply_schema(http: httpx.Client, schema: dict[str, Any]) -> list[str]:
    """返回所做变更的说明；无变更时返回空列表。"""
    changes: list[str] = []

    types = http.get("/api/v1/metadata/types", params={"category": "field", "limit": 1000})
    types.raise_for_status()
    type_ids = {t["name"]: t["id"] for t in types.json()["data"]}
    term_type = http.get(
        "/api/v1/metadata/types/name/glossaryTerm", params={"fields": "customProperties"}
    )
    term_type.raise_for_status()
    term = term_type.json()
    existing = {p["name"] for p in term.get("customProperties") or []}
    for prop in schema.get("customProperties", []):
        if prop["name"] in existing:
            continue
        resp = http.put(f"/api/v1/metadata/types/{term['id']}", json=_property_body(prop, type_ids))
        resp.raise_for_status()
        changes.append(f"自定义属性 {prop['name']}")

    setting = http.get(f"/api/v1/system/settings/{SETTING}")
    setting.raise_for_status()
    value = setting.json().get("config_value") or {}
    relations: list[dict[str, Any]] = list(value.get("relationTypes") or [])
    names = {r["name"] for r in relations}
    added = [r for r in schema.get("relationTypes", []) if r["name"] not in names]
    if added:
        resp = http.put(
            "/api/v1/system/settings",
            json={
                "config_type": SETTING,
                "config_value": {**value, "relationTypes": relations + added},
            },
        )
        resp.raise_for_status()
        changes += [f"关系类型 {r['name']}" for r in added]
    return changes


# 005：采集管理权限（R12，负责人 2026-11-07 确认）与 BFF 建档服务账号（R13）
ACCESS: dict[str, Any] = {
    "policies": [
        {
            "name": "ContextureSourcePolicy",
            "description": "织境 005：数据源、采集任务、测试连接与目录治理属性",
            "rules": [
                {
                    "name": "database-service",
                    "effect": "allow",
                    "resources": ["databaseService"],
                    "operations": ["Create", "ViewAll", "EditAll", "Deploy", "Trigger"],
                },
                {
                    "name": "ingestion-pipeline-and-workflow",
                    "effect": "allow",
                    "resources": ["ingestionPipeline", "workflow"],
                    "operations": ["Create", "ViewAll", "EditAll", "Deploy", "Trigger", "Delete"],
                },
                {
                    "name": "catalog-governance",
                    "effect": "allow",
                    "resources": ["database", "databaseSchema", "table"],
                    "operations": ["ViewAll", "EditAll"],
                },
            ],
        },
        {
            "name": "ContextureUserProvisionerPolicy",
            "description": "织境 005：BFF 在织境登录时建档用户并同步团队成员",
            "rules": [
                {
                    "name": "user",
                    "effect": "allow",
                    "resources": ["user"],
                    # 入组经 PATCH 团队 users（team 的 EditUsers）；PATCH 用户 teams 需要 EditAll，不采用（2026-11-07 实测）
                    "operations": ["Create", "ViewAll"],
                },
                {
                    "name": "team",
                    "effect": "allow",
                    "resources": ["team"],
                    "operations": ["ViewAll", "EditUsers"],
                },
            ],
        },
    ],
    "roles": [
        {"name": "ContextureSourceManager", "policies": ["ContextureSourcePolicy"]},
        {"name": "ContextureUserProvisioner", "policies": ["ContextureUserProvisionerPolicy"]},
    ],
    # 团队名与织境 realm 角色同名；成员由 BFF 在织境登录时按令牌角色同步（R13）
    "teams": [
        {"name": "admin", "teamType": "Group", "defaultRoles": ["ContextureSourceManager"]},
        {"name": "ai-engineer", "teamType": "Group", "defaultRoles": ["ContextureSourceManager"]},
    ],
    "users": [
        {
            "name": "service-account-contexture-bff",
            "email": "service-account-contexture-bff@contexture.local",
            "isBot": False,
            "roles": ["ContextureUserProvisioner"],
        }
    ],
}


def _get_by_name(http: httpx.Client, kind: str, name: str) -> dict[str, Any] | None:
    resp = http.get(f"/api/v1/{kind}/name/{name}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


def apply_access(http: httpx.Client, access: dict[str, Any] = ACCESS) -> list[str]:
    """创建缺失的策略、角色、团队与服务账号用户；已存在的不改。返回变更说明。"""
    changes: list[str] = []
    role_ids: dict[str, str] = {}
    for kind in ("policies", "roles", "teams", "users"):
        for item in access[kind]:
            existing = _get_by_name(http, kind, item["name"])
            if existing is None:
                body = dict(item)
                if kind == "teams":
                    body["defaultRoles"] = [role_ids[r] for r in item["defaultRoles"]]
                if kind == "users":
                    body["roles"] = [role_ids[r] for r in item["roles"]]
                resp = http.post(f"/api/v1/{kind}", json=body)
                resp.raise_for_status()
                existing = cast(dict[str, Any], resp.json())
                changes.append(f"{kind} {item['name']}")
            if kind == "roles":
                role_ids[item["name"]] = str(existing["id"])
    return changes


def provisioner_token() -> str:
    """以导入服务账号（client credentials）向 Keycloak 换取令牌。"""
    issuer = f"{os.environ['KEYCLOAK_URL']}/realms/{os.environ['KEYCLOAK_REALM']}"
    resp = httpx.post(
        f"{issuer}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["KEYCLOAK_PROVISIONER_CLIENT_ID"],
            "client_secret": os.environ["KEYCLOAK_PROVISIONER_CLIENT_SECRET"],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--om-url", default=os.environ.get("CTX_OM_URL", "http://localhost:8585"))
    args = parser.parse_args(argv[1:])
    token = os.environ.get("OM_TOKEN") or provisioner_token()
    with httpx.Client(base_url=args.om_url, timeout=30) as http:
        http.headers["Authorization"] = f"Bearer {token}"
        changes = apply_schema(http, load_schema()) + apply_access(http)
    print("om-config: " + ("；".join(changes) if changes else "无变更"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
