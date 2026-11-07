"""005 契约：/bff/v1/sources* 的状态码与响应结构（contracts/openapi/bff.yaml），以内存 OM 夹具运行真实代码。"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml
from bff_fakes import FakeObjectData, FakeObjectTypes, FakeOidc, FakeSessions, user_context
from fastapi.testclient import TestClient
from om_fake import FakeOM
from sources_helpers import service, upsert

from contexture_bff.api.deps import current_context
from contexture_bff.main import Services, create_app
from contexture_bff.settings import BffSettings

CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"
SPEC = yaml.safe_load((CONTRACTS / "openapi" / "bff.yaml").read_text())
ERROR = json.loads((CONTRACTS / "schemas" / "error.json").read_text())


def schema(name: str) -> dict[str, Any]:
    return {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]}


def check(body: Any, name: str) -> None:
    jsonschema.validate(body, schema(name))


def make(om: FakeOM, roles: tuple[str, ...] = ("ai-engineer",)) -> TestClient:
    app = create_app(
        BffSettings(tenant_id="local", public_url="http://testserver"),
        services=Services(
            sessions=FakeSessions(), oidc=FakeOidc(), object_types=FakeObjectTypes(),
            object_data=FakeObjectData(), authenticator=None, sources=service(om),
        ),
    )
    app.dependency_overrides[current_context] = lambda: user_context(roles=roles)
    return TestClient(app)


def test_create_get_list_match_contract_and_mask_password() -> None:
    om = FakeOM()
    c = make(om)
    resp = c.post("/bff/v1/sources", json=upsert())
    assert resp.status_code == 201, resp.text
    check(resp.json(), "SourceDetail")
    assert "secret-pw" not in resp.text
    got = c.get("/bff/v1/sources/mock-mes")
    assert got.status_code == 200
    check(got.json(), "SourceDetail")
    listed = c.get("/bff/v1/sources")
    assert listed.status_code == 200
    for item in listed.json()["data"]:
        check(item, "SourceSummary")
    assert "secret-pw" not in listed.text + got.text


def test_conflict_not_found_immutable_and_invalid() -> None:
    om = FakeOM()
    c = make(om)
    assert c.post("/bff/v1/sources", json=upsert()).status_code == 201
    dup = c.post("/bff/v1/sources", json=upsert())
    assert dup.status_code == 409 and dup.json()["code"] == "source.name_conflict"
    jsonschema.validate(dup.json(), ERROR)
    assert c.get("/bff/v1/sources/nope").json()["code"] == "source.not_found"
    imm = c.put("/bff/v1/sources/mock-mes", json=upsert(serviceType="Postgres", connection={**upsert()["connection"]}))
    assert imm.status_code == 400 and imm.json()["code"] == "source.immutable_field"
    bad = c.post("/bff/v1/sources", json=upsert(name="Bad_Name"))
    assert bad.status_code == 400


def test_test_connection_flow_matches_contract() -> None:
    c = make(FakeOM())
    started = c.post(
        "/bff/v1/sources/test-connection",
        json={"serviceType": "Mysql", "connection": upsert()["connection"]},
    )
    assert started.status_code == 202
    check(started.json(), "TestConnectionResult")
    result = c.get(f"/bff/v1/sources/test-connection/{started.json()['workflowId']}")
    assert result.status_code == 200
    check(result.json(), "TestConnectionResult")


def test_upstream_unavailable_is_502_without_data() -> None:
    om = FakeOM()
    om.down = True
    resp = make(om).get("/bff/v1/sources")
    assert resp.status_code == 502
    assert resp.json()["code"] == "upstream.unavailable"
    assert "data" not in resp.json()


@pytest.mark.parametrize("method,path", [("GET", "/bff/v1/sources"), ("POST", "/bff/v1/sources")])
def test_business_user_forbidden(method: str, path: str) -> None:
    resp = make(FakeOM(), roles=("business-user",)).request(method, path, json=upsert())
    assert resp.status_code == 403
