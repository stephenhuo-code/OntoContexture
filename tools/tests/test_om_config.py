"""OM 本体配置初始化：只新增缺失的自定义属性与关系类型，已存在的不改，重复执行无变化。"""

import json
from typing import Any

import httpx

from tools.om_config import apply_schema, load_schema

TYPES = {"string": "t-string", "enum": "t-enum", "entityReference": "t-ref"}


class FakeOM:
    def __init__(self, existing_props: list[str], relations: list[dict[str, Any]]) -> None:
        self.props = list(existing_props)
        self.relations = relations
        self.puts: list[dict[str, Any]] = []

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            assert req.headers["authorization"] == "Bearer tok"
            path = req.url.path
            if path == "/api/v1/metadata/types" and req.method == "GET":
                data = [{"id": i, "name": n} for n, i in TYPES.items()]
                return httpx.Response(200, json={"data": data})
            if path == "/api/v1/metadata/types/name/glossaryTerm":
                props = [{"name": p} for p in self.props]
                return httpx.Response(200, json={"id": "gt", "customProperties": props})
            if path == "/api/v1/metadata/types/gt" and req.method == "PUT":
                body = json.loads(req.content)
                self.puts.append(body)
                self.props.append(body["name"])
                return httpx.Response(200, json={})
            if path == "/api/v1/system/settings/glossaryTermRelationSettings":
                value = {"relationTypes": self.relations}
                return httpx.Response(200, json={"config_type": "x", "config_value": value})
            if path == "/api/v1/system/settings" and req.method == "PUT":
                self.relations = json.loads(req.content)["config_value"]["relationTypes"]
                return httpx.Response(200, json={})
            raise AssertionError(f"unexpected {req.method} {path}")

        return httpx.MockTransport(handler)


def run(om: FakeOM) -> list[str]:
    with httpx.Client(base_url="http://om", transport=om.transport()) as http:
        http.headers["Authorization"] = "Bearer tok"
        return apply_schema(http, load_schema())


def test_creates_missing_properties_with_types() -> None:
    om = FakeOM(existing_props=["ctx_kind"], relations=[{"name": "relatedTo"}])
    changes = run(om)
    names = [p["name"] for p in om.puts]
    assert "ctx_kind" not in names
    assert {"ctx_uri", "ctx_data_type", "ctx_link_source"} <= set(names)
    enum = next(p for p in om.puts if p["name"] == "ctx_required")
    assert enum["propertyType"] == {"id": "t-enum", "type": "type"}
    assert enum["customPropertyConfig"]["config"]["values"] == ["是", "否"]
    ref = next(p for p in om.puts if p["name"] == "ctx_link_target")
    assert ref["customPropertyConfig"]["config"] == ["glossaryTerm"]
    assert any("hasProperty" in c for c in changes)


def test_keeps_existing_relation_types() -> None:
    om = FakeOM(existing_props=[], relations=[{"name": "relatedTo"}, {"name": "broader"}])
    run(om)
    assert [r["name"] for r in om.relations] == ["relatedTo", "broader", "hasProperty"]
    has = om.relations[-1]
    assert has["category"] == "associative"
    assert has["displayName"] == "具有属性"


def test_idempotent() -> None:
    om = FakeOM(existing_props=[], relations=[])
    run(om)
    puts = len(om.puts)
    assert run(om) == []
    assert len(om.puts) == puts


# ---------- 005：采集管理权限与 BFF 建档服务账号（research R12、R13） ----------
from tools.om_config import ACCESS, apply_access  # noqa: E402


class FakeAccessOM:
    """按名称存取 policies / roles / teams / users；GET 不存在返回 404，POST 新建。"""

    def __init__(self, existing: dict[str, dict[str, dict[str, Any]]] | None = None) -> None:
        self.store: dict[str, dict[str, dict[str, Any]]] = {
            k: dict((existing or {}).get(k, {})) for k in ("policies", "roles", "teams", "users")
        }
        self.writes: list[tuple[str, str, dict[str, Any]]] = []

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            parts = req.url.path.removeprefix("/api/v1/").split("/")
            kind = parts[0]
            assert kind in self.store, req.url.path
            if req.method == "GET" and parts[1:2] == ["name"]:
                found = self.store[kind].get(parts[2])
                return httpx.Response(200, json=found) if found else httpx.Response(404, json={})
            if req.method == "POST" and len(parts) == 1:
                body = json.loads(req.content)
                self.writes.append((req.method, kind, body))
                self.store[kind][body["name"]] = {"id": f"{kind}-{body['name']}", **body}
                return httpx.Response(201, json=self.store[kind][body["name"]])
            raise AssertionError(f"unexpected {req.method} {req.url.path}")

        return httpx.MockTransport(handler)


def run_access(om: FakeAccessOM) -> list[str]:
    with httpx.Client(base_url="http://om", transport=om.transport()) as http:
        return apply_access(http, ACCESS)


def test_access_creates_policies_roles_teams_and_service_user() -> None:
    om = FakeAccessOM()
    run_access(om)
    source = om.store["policies"]["ContextureSourcePolicy"]
    rules = {tuple(r["resources"]): set(r["operations"]) for r in source["rules"]}
    assert rules[("databaseService",)] == {"Create", "ViewAll", "EditAll", "Deploy", "Trigger"}
    assert rules[("ingestionPipeline", "workflow")] == {
        "Create",
        "ViewAll",
        "EditAll",
        "Deploy",
        "Trigger",
        "Delete",
    }
    assert rules[("database", "databaseSchema", "table")] == {"ViewAll", "EditAll"}
    assert all(r["effect"] == "allow" for r in source["rules"])
    provisioner = om.store["policies"]["ContextureUserProvisionerPolicy"]
    rules = {tuple(r["resources"]): set(r["operations"]) for r in provisioner["rules"]}
    assert rules == {("user",): {"Create", "ViewAll"}, ("team",): {"ViewAll", "EditUsers"}}
    assert om.store["roles"]["ContextureSourceManager"]["policies"] == ["ContextureSourcePolicy"]
    for team in ("admin", "ai-engineer"):
        assert om.store["teams"][team]["teamType"] == "Group"
        assert om.store["teams"][team]["defaultRoles"] == ["roles-ContextureSourceManager"]
    user = om.store["users"]["service-account-contexture-bff"]
    assert user["roles"] == ["roles-ContextureUserProvisioner"]
    assert user["isBot"] is False
    assert user["email"].endswith("@contexture.local")


def test_access_is_idempotent_and_keeps_existing() -> None:
    om = FakeAccessOM()
    run_access(om)
    writes = len(om.writes)
    assert run_access(om) == []
    assert len(om.writes) == writes


def test_access_does_not_grant_delete_on_database_service() -> None:
    for policy in ACCESS["policies"]:
        for rule in policy["rules"]:
            if "databaseService" in rule["resources"]:
                assert "Delete" not in rule["operations"]
