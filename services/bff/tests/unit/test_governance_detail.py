"""006 术语与标签只读详情：字段按 research R9 已确认的清单逐项映射（FR-013）。"""

import pytest
from assets_helpers import reader, seed
from bff_fakes import user_context
from om_fake import FakeOM

from contexture_bff.adapters.om_assets import GLOSSARY_TERM_FIELDS, TAG_FIELDS
from contexture_core.errors import ContextureError

TERM_KEYS = {
    "ref", "name", "displayName", "description", "glossary", "parent", "synonyms", "relatedTerms",
    "references", "owners", "reviewers", "domains", "tags", "entityStatus", "origin",
}  # fmt: skip
TAG_KEYS = {
    "ref", "name", "displayName", "description", "classification", "parent", "owners",
    "reviewers", "domains", "deprecated",
}  # fmt: skip


def test_requested_fields() -> None:
    assert set(GLOSSARY_TERM_FIELDS.split(",")) >= {
        "owners",
        "reviewers",
        "domains",
        "tags",
        "relatedTerms",
    }
    assert set(TAG_FIELDS.split(",")) >= {"owners", "reviewers", "domains"}


async def test_glossary_term_detail_maps_confirmed_fields() -> None:
    om = FakeOM()
    seed(om)
    d = await reader(om).glossary_term(user_context(), "ContextureDevGlossary.工单")
    assert set(d) == TERM_KEYS
    assert d["glossary"]["name"] == "ContextureDevGlossary"
    assert d["synonyms"] == ["Work Order"]
    assert d["references"] == [{"name": "手册", "endpoint": "https://example.invalid/wo"}]
    assert d["entityStatus"] == "Approved" and d["origin"] == "devTest"
    assert ("GET", "/glossaryTerms/name/ContextureDevGlossary.工单") in om.calls


async def test_tag_detail_maps_confirmed_fields() -> None:
    om = FakeOM()
    seed(om)
    d = await reader(om).tag(user_context(), "数据级别.一级")
    assert set(d) == TAG_KEYS
    assert d["classification"]["name"] == "数据级别"
    assert d["deprecated"] is False


@pytest.mark.parametrize("method", ["glossary_term", "tag"])
async def test_missing_is_catalog_not_found(method: str) -> None:
    with pytest.raises(ContextureError) as ei:
        await getattr(reader(FakeOM()), method)(user_context(), "none.none")
    assert (ei.value.code, ei.value.status_code) == ("catalog.not_found", 404)
