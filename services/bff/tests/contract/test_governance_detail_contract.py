"""006 契约：getGlossaryTermDetail、getTagDetail（FR-013）。"""

from assets_helpers import seed
from contract_helpers import check, make
from om_fake import FakeOM

EDITABLE = {"patch", "editable", "actions"}


def test_details_match_contract_and_are_read_only() -> None:
    om = FakeOM()
    seed(om)
    c = make(om)
    term = c.get("/bff/v1/governance/glossary-terms/ContextureDevGlossary.工单")
    assert term.status_code == 200, term.text
    check(term.json(), "GlossaryTermDetail")
    tag = c.get("/bff/v1/governance/tags/数据级别.一级")
    assert tag.status_code == 200, tag.text
    check(tag.json(), "TagDetail")
    for body in (term.json(), tag.json()):
        assert not EDITABLE & set(body)
    for path in ("/bff/v1/governance/glossary-terms/x.none", "/bff/v1/governance/tags/x.none"):
        r = c.get(path)
        assert (r.status_code, r.json()["code"]) == (404, "catalog.not_found")
