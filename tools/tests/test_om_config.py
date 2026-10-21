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
