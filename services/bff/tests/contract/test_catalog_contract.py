"""US3 契约：GET /bff/v1/catalog/{entityType}/{fqn}。"""

from contract_helpers import check, make
from om_fake import FakeOM
from sources_helpers import upsert


def test_catalog_entities_match_contract() -> None:
    om = FakeOM()
    c = make(om)
    assert c.post("/bff/v1/sources", json=upsert()).status_code == 201
    om.add_tables(
        "mock-mes", "default", "mes", {"work_order": [("wo_no", "varchar(20)", "PRIMARY_KEY")]}
    )
    for etype, fqn in [
        ("databaseService", "mock-mes"),
        ("database", "mock-mes.default"),
        ("databaseSchema", "mock-mes.default.mes"),
        ("table", "mock-mes.default.mes.work_order"),
    ]:
        resp = c.get(f"/bff/v1/catalog/{etype}/{fqn}")
        assert resp.status_code == 200, resp.text
        check(resp.json(), "CatalogEntity")
    assert (
        c.get("/bff/v1/catalog/table/mock-mes.default.mes.none").json()["code"]
        == "catalog.not_found"
    )
    assert c.get("/bff/v1/catalog/view/x").status_code == 422
