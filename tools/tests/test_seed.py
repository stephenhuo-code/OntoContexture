"""make seed：OM 建“设备”对象与属性（已审批、hasProperty 关联），Doris 建表写 10 行。幂等。"""

import json
from typing import Any

import httpx

from tools.seed import DORIS_SQL, EQUIPMENT_ROWS, seed_om


class FakeOM:
    def __init__(self) -> None:
        self.glossaries: dict[str, dict[str, Any]] = {}
        self.classifications: dict[str, dict[str, Any]] = {}
        self.tags: dict[str, dict[str, Any]] = {}
        self.terms: dict[str, dict[str, Any]] = {}
        self.patches: list[tuple[str, Any]] = []

    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            p = req.url.path.removeprefix("/api/v1")
            body = json.loads(req.content) if req.content else {}
            if req.method == "GET":
                for prefix, store in (
                    ("/glossaries/name/", self.glossaries),
                    ("/classifications/name/", self.classifications),
                    ("/tags/name/", self.tags),
                    ("/glossaryTerms/name/", self.terms),
                ):
                    if p.startswith(prefix):
                        key = p.removeprefix(prefix)
                        return (
                            httpx.Response(200, json=store[key])
                            if key in store
                            else httpx.Response(404)
                        )
            if req.method == "POST":
                if p == "/glossaries":
                    self.glossaries[body["name"]] = {"id": "g-" + body["name"], **body}
                    return httpx.Response(201, json=self.glossaries[body["name"]])
                if p == "/classifications":
                    self.classifications[body["name"]] = {"id": "c", **body}
                    return httpx.Response(201, json={})
                if p == "/tags":
                    fqn = f"{body['classification']}.{body['name']}"
                    self.tags[fqn] = {"id": fqn, **body}
                    return httpx.Response(201, json={})
                if p == "/glossaryTerms":
                    fqn = f"{body['glossary']}.{body['name']}"
                    term = {
                        "id": "t-" + body["name"],
                        "fullyQualifiedName": fqn,
                        "entityStatus": "Approved",
                        "relatedTerms": [],
                        **body,
                    }
                    self.terms[fqn] = term
                    return httpx.Response(201, json=term)
            if req.method == "PATCH" and p.startswith("/glossaryTerms/"):
                assert req.headers["content-type"] == "application/json-patch+json"
                tid = p.removeprefix("/glossaryTerms/")
                self.patches.append((tid, body))
                term = next(t for t in self.terms.values() if t["id"] == tid)
                for op in body:
                    term["relatedTerms"].append(op["value"])
                return httpx.Response(200, json=term)
            raise AssertionError(f"unexpected {req.method} {p}")

        return httpx.MockTransport(handler)


def run(om: FakeOM) -> None:
    with httpx.Client(base_url="http://om", transport=om.transport()) as http:
        seed_om(http, glossary="quality")


def test_creates_object_and_properties() -> None:
    om = FakeOM()
    run(om)
    eq = om.terms["quality.Equipment"]
    assert eq["extension"]["ctx_kind"] == ["object"]
    assert eq["extension"]["ctx_uri"] == "urn:ctx:object:quality:Equipment"
    code = om.terms["quality.code"]
    assert code["extension"] == {
        "ctx_kind": ["property"],
        "ctx_uri": "urn:ctx:property:quality:code",
        "ctx_data_type": ["string"],
        "ctx_required": ["是"],
        "ctx_key": ["主键"],
    }
    assert code["tags"] == [{"tagFQN": "数据级别.一级", "source": "Classification"}]
    rels = [r for r in eq["relatedTerms"] if r["relationType"] == "hasProperty"]
    assert len(rels) == 5
    assert "数据级别.三级" in om.tags


def test_idempotent() -> None:
    om = FakeOM()
    run(om)
    patches = len(om.patches)
    run(om)
    assert len(om.patches) == patches


def test_doris_rows_and_sql() -> None:
    assert len(EQUIPMENT_ROWS) == 10
    assert all(r[0].startswith("CNC-") for r in EQUIPMENT_ROWS)
    joined = "\n".join(DORIS_SQL)
    assert "CREATE TABLE IF NOT EXISTS equipment" in joined
    assert '"replication_num" = "1"' in joined
