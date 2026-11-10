"""006 契约：getAssetSummary（FR-012）。"""

from assets_helpers import TABLE_FQN, seed
from contract_helpers import check, make
from om_fake import FakeOM


def test_summary_matches_contract() -> None:
    om = FakeOM()
    seed(om)
    c = make(om)
    t = c.get(f"/bff/v1/assets/summary/table/{TABLE_FQN}")
    assert t.status_code == 200, t.text
    check(t.json(), "AssetSummary")
    assert t.json()["columns"]
    col = c.get(f"/bff/v1/assets/summary/tableColumn/{TABLE_FQN}.wo_no")
    assert col.status_code == 200, col.text
    check(col.json(), "AssetSummary")
    assert col.json()["column"]["name"] == "wo_no" and col.json()["parentTable"]["fqn"] == TABLE_FQN
    g = c.get("/bff/v1/assets/summary/glossaryTerm/ContextureDevGlossary.工单")
    assert g.status_code == 200, g.text
    check(g.json(), "AssetSummary")
    missing = c.get("/bff/v1/assets/summary/table/x.y.z.none")
    assert (missing.status_code, missing.json()["code"]) == (404, "catalog.not_found")
