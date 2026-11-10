"""006 契约：searchAssets、countAssetTypes、suggestAssets（FR-004、FR-005、FR-007、FR-019）。"""

import httpx
from assets_helpers import seed
from contract_helpers import check, make
from om_fake import FakeOM

BAD = [
    {"pageSize": 20},
    {"scope": "table", "entityType": "tag"},
    {"filters": {"color": {"values": ["x"]}}},
    {"filters": {"column": {"values": ["x"]}}},
    {"keyword": "x" * 201},
]


def test_search_matches_contract_and_rejects_invalid_criteria() -> None:
    om = FakeOM()
    seed(om)
    c = make(om)
    resp = c.post("/bff/v1/assets/search", json={"keyword": "工单"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    check(body, "SearchPage")
    assert body["total"] >= 1
    for raw in BAD:
        r = c.post("/bff/v1/assets/search", json=raw)
        assert r.status_code == 422, raw
        assert r.json()["code"] in ("search.invalid_criteria", "request.invalid"), r.text
        assert set(r.json()) >= {"code", "message", "trace_id"}
    r = c.post("/bff/v1/assets/search", json={"page": 668, "pageSize": 15})
    assert (r.status_code, r.json()["code"]) == (422, "search.window_exceeded")


def test_search_upstream_errors() -> None:
    om = FakeOM()
    c = make(om)
    om.search_error = httpx.Response(500, json={"code": 500, "message": "Failed to find index x"})
    r = c.post("/bff/v1/assets/search", json={})
    assert (r.status_code, r.json()["code"]) == (503, "search.index_missing")
    om.search_error = None
    om.search_timed_out = True
    r = c.post("/bff/v1/assets/search", json={})
    assert (r.status_code, r.json()["code"]) == (504, "search.timeout")
    om.search_timed_out = False
    om.connect_error = True
    r = c.post("/bff/v1/assets/search", json={})
    assert (r.status_code, r.json()["code"]) == (502, "upstream.unavailable")


def test_type_counts_contract_and_default_type() -> None:
    om = FakeOM()
    seed(om)
    r = make(om).post("/bff/v1/assets/type-counts", json={"keyword": "工单"})
    assert r.status_code == 200, r.text
    body = r.json()
    check(body, "TypeCounts")
    assert all(x["count"] > 0 for x in body["counts"])
    assert body["defaultType"] == body["topHitType"]


def test_suggestions_contract() -> None:
    om = FakeOM()
    seed(om)
    r = make(om).get("/bff/v1/assets/suggestions", params={"keyword": "wo_no"})
    assert r.status_code == 200, r.text
    groups = r.json()["groups"]
    for g in groups:
        assert len(g["items"]) <= 5
        for item in g["items"]:
            check(item, "Suggestion")
    col = next(g for g in groups if g["entityType"] == "tableColumn")
    assert col["items"][0]["parentTable"]["fqn"].endswith("work_order")
