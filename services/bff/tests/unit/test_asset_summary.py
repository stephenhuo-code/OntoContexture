"""006 摘要读取：按身份读取 OM 实体；列读取所属表（research R9、R10；FR-012、FR-014）。"""

import pytest
from assets_helpers import TABLE_FQN, reader, seed
from bff_fakes import user_context
from om_fake import FakeOM

from contexture_bff.adapters.om_assets import SUMMARY_FIELDS, parent_table_fqn
from contexture_core.errors import ContextureError


def test_summary_fields_per_type() -> None:
    assert (
        SUMMARY_FIELDS["table"]
        == "owners,domains,tags,dataProducts,columns,tableConstraints,certification"
    )
    assert SUMMARY_FIELDS["database"] == "owners,domains,tags,dataProducts,certification"
    assert SUMMARY_FIELDS["databaseSchema"] == "owners,domains,tags,dataProducts,certification"
    assert SUMMARY_FIELDS["glossaryTerm"] == "owners,domains,tags,reviewers"
    assert SUMMARY_FIELDS["tag"] == "owners,domains,reviewers"
    assert SUMMARY_FIELDS["*"] == "owners,domains,tags"


def test_parent_table_fqn_respects_quotes() -> None:
    assert parent_table_fqn('s.d.sc."a.b".col') == 's.d.sc."a.b"'
    assert parent_table_fqn("s.d.sc.t.col") == "s.d.sc.t"


async def test_table_summary_reads_entity_and_splits_tags() -> None:
    om = FakeOM()
    seed(om)
    s = await reader(om).summary(user_context(), "table", TABLE_FQN)
    assert s["ref"]["entityType"] == "table" and s["ref"]["fqn"] == TABLE_FQN
    assert s["governance"]["origin"] == "devTest"
    assert s["governance"]["tier"] == "Tier.Tier1"
    cols = {c["name"]: c for c in s["columns"]}
    assert cols["wo_no"]["constraint"] == "PRIMARY_KEY"
    assert cols["wo_no"]["dataLevel"] == "数据级别.一级"
    assert ("GET", f"/tables/name/{TABLE_FQN}") in om.calls


async def test_column_summary_reads_parent_table() -> None:
    om = FakeOM()
    seed(om)
    s = await reader(om).summary(user_context(), "tableColumn", f"{TABLE_FQN}.wo_no")
    assert s["column"]["name"] == "wo_no"
    assert s["parentTable"]["fqn"] == TABLE_FQN
    assert s["ref"]["entityType"] == "tableColumn"


async def test_unknown_fqn_is_catalog_not_found() -> None:
    om = FakeOM()
    with pytest.raises(ContextureError) as ei:
        await reader(om).summary(user_context(), "table", "x.y.z.none")
    assert (ei.value.code, ei.value.status_code) == ("catalog.not_found", 404)


async def test_summary_and_details_decode_html_entities() -> None:
    om = FakeOM()
    seed(om)
    table = next(t for t in om.tables if t["fullyQualifiedName"] == TABLE_FQN)
    table["description"] = "生产工单&#xff1a;主表"
    table["columns"][0]["description"] = "工单号&#xff1a;唯一"
    om.glossary_terms["ContextureDevGlossary.工单"]["description"] = "设备属性&#xff1a;投产日期"
    om.tag_entities["数据级别.一级"]["description"] = "公开&amp;内部"
    r = reader(om)
    s = await r.summary(user_context(), "table", TABLE_FQN)
    assert s["description"] == "生产工单：主表"
    assert s["columns"][0]["description"] == "工单号：唯一"
    assert (await r.summary(user_context(), "glossaryTerm", "ContextureDevGlossary.工单"))[
        "description"
    ] == "设备属性：投产日期"
    assert (await r.glossary_term(user_context(), "ContextureDevGlossary.工单"))[
        "description"
    ] == "设备属性：投产日期"
    assert (await r.tag(user_context(), "数据级别.一级"))["description"] == "公开&内部"
