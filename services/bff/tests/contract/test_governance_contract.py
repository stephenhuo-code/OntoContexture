"""US4 契约：PATCH /bff/v1/catalog/{entityType}/{fqn} 与 GET /bff/v1/governance/options。"""

from contract_helpers import check, make
from om_fake import FakeOM
from sources_helpers import upsert

TABLE = "mock-mes.default.mes.work_order"
D1 = {"id": "d1000000-0000-4000-8000-000000000001", "type": "domain", "name": "Production"}


def client() -> tuple[FakeOM, object]:
    om = FakeOM()
    om.options.update(
        domains=[D1],
        classifications=[{"name": "PII", "mutuallyExclusive": True}],
        tags=[{"name": "Sensitive", "fullyQualifiedName": "PII.Sensitive"}],
    )
    c = make(om)
    assert c.post("/bff/v1/sources", json=upsert()).status_code == 201
    om.add_tables("mock-mes", "default", "mes", {"work_order": ["wo_no", "qty"]})
    return om, c


def test_patch_and_clear_match_contract() -> None:
    _, c = client()
    resp = c.patch(
        f"/bff/v1/catalog/table/{TABLE}",
        json={"displayName": "工单", "domain": {"id": D1["id"], "type": "domain"}},
    )
    assert resp.status_code == 200, resp.text
    check(resp.json(), "CatalogEntity")
    assert resp.json()["governance"]["displayName"] == "工单"
    resp = c.patch(f"/bff/v1/catalog/table/{TABLE}", json={"displayName": None, "domain": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["governance"]["displayName"] is None
    assert resp.json()["governance"]["domains"] == []
    resp = c.patch(
        f"/bff/v1/catalog/table/{TABLE}", json={"columnName": "qty", "description": "数量"}
    )
    assert resp.status_code == 200, resp.text


def test_patch_rejections() -> None:
    _, c = client()
    for body, code in [
        ({"columnName": "qty", "tier": "Tier.Tier1"}, "governance.field_not_allowed"),
        ({"retentionPeriod": "30 days"}, "governance.invalid_retention"),
        ({"tags": ["PII.Sensitive", "PII.Other"]}, "governance.exclusive_tags"),
    ]:
        resp = c.patch(f"/bff/v1/catalog/table/{TABLE}", json=body)
        assert (resp.status_code, resp.json()["code"]) == (400, code), resp.text
        check(resp.json(), "Error")
    assert c.patch(f"/bff/v1/catalog/table/{TABLE}", json={"unknown": 1}).status_code == 422
    assert (
        c.patch(f"/bff/v1/catalog/table/{TABLE}", json={"tags": "PII.Sensitive"}).status_code == 422
    )


def test_governance_options_match_contract() -> None:
    _, c = client()
    resp = c.get("/bff/v1/governance/options")
    assert resp.status_code == 200, resp.text
    check(resp.json(), "GovernanceOptions")
    assert resp.json()["classifications"] == [
        {"name": "PII", "mutuallyExclusive": True, "tags": ["PII.Sensitive"]}
    ]
