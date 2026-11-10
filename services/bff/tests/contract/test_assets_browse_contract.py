"""006 契约：browseAssets、getAssetFacet（FR-006、FR-008）。"""

from assets_helpers import seed
from contract_helpers import check, make
from om_fake import FakeOM


def test_browse_contract() -> None:
    om = FakeOM()
    seed(om)
    c = make(om)
    r = c.post("/bff/v1/assets/browse", json={"criteria": {}, "parentPath": []})
    assert r.status_code == 200, r.text
    nodes = r.json()["nodes"]
    for n in nodes:
        check(n, "BrowseNode")
        assert n["count"] > 0
    assert {n["value"] for n in nodes} >= {"databases", "governance"}
    child = c.post(
        "/bff/v1/assets/browse",
        json={"criteria": {}, "parentPath": [{"level": "root", "value": "databases"}]},
    )
    assert child.status_code == 200, child.text
    assert all(n["level"] == "serviceType" for n in child.json()["nodes"])
    skip = c.post(
        "/bff/v1/assets/browse",
        json={
            "criteria": {},
            "parentPath": [
                {"level": "root", "value": "databases"},
                {"level": "service", "value": "x"},
            ],
        },
    )
    assert (skip.status_code, skip.json()["code"]) == (422, "search.invalid_criteria")
    too_deep = c.post(
        "/bff/v1/assets/browse",
        json={"criteria": {}, "parentPath": [{"level": "root", "value": "databases"}] * 6},
    )
    assert too_deep.status_code == 422


def test_facet_contract() -> None:
    om = FakeOM()
    seed(om)
    c = make(om)
    for dim, none in [("owner", True), ("tier", True), ("service", False), ("dataProduct", False)]:
        r = c.post("/bff/v1/assets/facets", json={"criteria": {}, "dimension": dim})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["supportsNone"] is none
        for o in body["options"]:
            check(o, "FacetOption")
            assert o["value"] != "无"
    bad = c.post("/bff/v1/assets/facets", json={"criteria": {}, "dimension": "column"})
    assert (bad.status_code, bad.json()["code"]) == (422, "search.invalid_criteria")
    long = c.post(
        "/bff/v1/assets/facets",
        json={"criteria": {}, "dimension": "tier", "optionQuery": "x" * 101},
    )
    assert long.status_code == 422
