"""US4：治理属性 → OM JSON Patch、校验与继承来源（规则按 OM 2.0.3 setInheritedFields 核实）。"""

from typing import Any

import pytest
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import service, upsert

from contexture_core.errors import ContextureError

D1 = {
    "id": "d1000000-0000-4000-8000-000000000001",
    "type": "domain",
    "name": "Production",
    "fullyQualifiedName": "Production",
}
D2 = {
    "id": "d2000000-0000-4000-8000-000000000002",
    "type": "domain",
    "name": "Quality",
    "fullyQualifiedName": "Quality",
}
U1 = {"id": "a1000000-0000-4000-8000-000000000001", "type": "user", "name": "engineer1"}
U2 = {"id": "a2000000-0000-4000-8000-000000000002", "type": "user", "name": "admin1"}
T1 = {"id": "b1000000-0000-4000-8000-000000000001", "type": "team", "name": "ai-engineer"}
T2 = {"id": "b2000000-0000-4000-8000-000000000002", "type": "team", "name": "admin"}
P1 = {
    "id": "c1000000-0000-4000-8000-000000000001",
    "type": "dataProduct",
    "name": "MES 工单",
    "fullyQualifiedName": "MES 工单",
}
P2 = {
    "id": "c2000000-0000-4000-8000-000000000002",
    "type": "dataProduct",
    "name": "质量追溯",
    "fullyQualifiedName": "质量追溯",
}
SVC, DB, SCHEMA, TABLE = (
    "mock-mes",
    "mock-mes.default",
    "mock-mes.default.mes",
    "mock-mes.default.mes.work_order",
)


def ref(r: dict[str, Any]) -> dict[str, Any]:
    return {"id": r["id"], "type": r["type"]}


async def setup() -> tuple[FakeOM, Any]:
    om = FakeOM()
    om.options.update(
        users=[
            {**U1, "isBot": False},
            {**U2, "isBot": False},
            {
                "id": "e0000000-0000-4000-8000-000000000000",
                "type": "user",
                "name": "ingestion-bot",
                "isBot": True,
            },
        ],
        teams=[{**T1, "teamType": "Group"}, {**T2, "teamType": "Group"}],
        domains=[D1, D2],
        dataProducts=[{**P1, "domains": [D1]}, {**P2, "domains": [D2]}],
        classifications=[
            {"name": "PII", "mutuallyExclusive": True},
            {"name": "PersonalData", "mutuallyExclusive": True},
            {"name": "Tier", "mutuallyExclusive": True},
            {"name": "Certification", "mutuallyExclusive": True},
            {"name": "Source", "mutuallyExclusive": False},
        ],
        tags=[
            {"name": "Sensitive", "fullyQualifiedName": "PII.Sensitive"},
            {"name": "NonSensitive", "fullyQualifiedName": "PII.NonSensitive"},
            {"name": "Personal", "fullyQualifiedName": "PersonalData.Personal"},
            {"name": "Tier1", "fullyQualifiedName": "Tier.Tier1"},
            {"name": "Gold", "fullyQualifiedName": "Certification.Gold"},
            {"name": "MES", "fullyQualifiedName": "Source.MES"},
            {"name": "ERP", "fullyQualifiedName": "Source.ERP"},
        ],
        glossaryTerms=[{"name": "Quantity", "fullyQualifiedName": "Glossary.Quantity"}],
    )
    svc = service(om)
    await svc.create_source(user_context(), upsert())
    om.add_tables(SVC, "default", "mes", {"work_order": ["wo_no", "qty"], "line": ["code"]})
    return om, svc


async def patch(svc: Any, etype: str, fqn: str, body: dict[str, Any]) -> dict[str, Any]:
    return await svc.patch_catalog_entity(user_context(), etype, fqn, body)


async def gov(svc: Any, etype: str, fqn: str) -> dict[str, Any]:
    return (await svc.get_catalog_entity(user_context(), etype, fqn))["governance"]


async def reject(svc: Any, etype: str, fqn: str, body: dict[str, Any]) -> ContextureError:
    with pytest.raises(ContextureError) as exc:
        await patch(svc, etype, fqn, body)
    return exc.value


async def test_domain_inherits_from_service_down_to_table() -> None:
    _, svc = await setup()
    await patch(svc, "databaseService", SVC, {"domain": ref(D1)})
    for etype, fqn in [("database", DB), ("databaseSchema", SCHEMA), ("table", TABLE)]:
        g = await gov(svc, etype, fqn)
        assert [d["id"] for d in g["domains"]] == [D1["id"]]
        assert g["inheritedFrom"]["domains"] == {
            "entityType": "databaseService",
            "fullyQualifiedName": SVC,
        }
    await patch(svc, "databaseSchema", SCHEMA, {"domain": ref(D2)})
    g = await gov(svc, "table", TABLE)
    assert [d["id"] for d in g["domains"]] == [D2["id"]]
    assert g["inheritedFrom"]["domains"] == {
        "entityType": "databaseSchema",
        "fullyQualifiedName": SCHEMA,
    }
    assert "domains" not in (await gov(svc, "databaseSchema", SCHEMA))["inheritedFrom"]


async def test_owners_do_not_flow_from_service_to_database() -> None:
    _, svc = await setup()
    await patch(svc, "databaseService", SVC, {"owners": [ref(U1)]})
    g = await gov(svc, "database", DB)
    assert g["owners"] == [] and "owners" not in g["inheritedFrom"]
    await patch(svc, "database", DB, {"owners": [ref(U2)]})
    g = await gov(svc, "table", TABLE)
    assert [o["id"] for o in g["owners"]] == [U2["id"]]
    assert g["inheritedFrom"]["owners"] == {"entityType": "database", "fullyQualifiedName": DB}


async def test_retention_inherits_and_clearing_restores_inheritance() -> None:
    _, svc = await setup()
    await patch(svc, "database", DB, {"retentionPeriod": "P30D"})
    await patch(svc, "databaseSchema", SCHEMA, {"retentionPeriod": "PT24H"})
    g = await gov(svc, "table", TABLE)
    assert g["retentionPeriod"] == "PT24H"
    assert g["inheritedFrom"]["retentionPeriod"]["fullyQualifiedName"] == SCHEMA
    await patch(svc, "databaseSchema", SCHEMA, {"retentionPeriod": None})
    g = await gov(svc, "table", TABLE)
    assert g["retentionPeriod"] == "P30D"
    assert g["inheritedFrom"]["retentionPeriod"] == {
        "entityType": "database",
        "fullyQualifiedName": DB,
    }


async def test_patch_is_converted_to_om_json_patch() -> None:
    om, svc = await setup()
    await patch(
        svc,
        "table",
        TABLE,
        {
            "displayName": "工单",
            "tier": "Tier.Tier1",
            "tags": ["PII.Sensitive"],
            "glossaryTerms": ["Glossary.Quantity"],
        },
    )
    fqn, ops = om.patches[-1]
    assert fqn == TABLE
    assert {"op": "add", "path": "/displayName", "value": "工单"} in ops
    tags = next(o for o in ops if o["path"] == "/tags")["value"]
    assert {(t["tagFQN"], t["source"], t["labelType"]) for t in tags} == {
        ("Tier.Tier1", "Classification", "Manual"),
        ("PII.Sensitive", "Classification", "Manual"),
        ("Glossary.Quantity", "Glossary", "Manual"),
    }
    g = await gov(svc, "table", TABLE)
    assert (g["displayName"], g["tier"], g["tags"], g["glossaryTerms"]) == (
        "工单",
        "Tier.Tier1",
        ["PII.Sensitive"],
        ["Glossary.Quantity"],
    )
    # 只改分类标签时保留 Tier 与术语；清空显示名称转为 remove
    await patch(svc, "table", TABLE, {"tags": [], "displayName": None})
    _, ops = om.patches[-1]
    assert {"op": "remove", "path": "/displayName"} in ops
    g = await gov(svc, "table", TABLE)
    assert (g["displayName"], g["tier"], g["tags"], g["glossaryTerms"]) == (
        None,
        "Tier.Tier1",
        [],
        ["Glossary.Quantity"],
    )


async def test_data_product_must_match_effective_domain() -> None:
    _, svc = await setup()
    await patch(svc, "databaseService", SVC, {"domain": ref(D1)})
    exc = await reject(svc, "table", TABLE, {"dataProducts": [ref(P2)]})
    assert exc.code == "governance.domain_mismatch" and exc.status_code == 400
    await patch(svc, "table", TABLE, {"dataProducts": [ref(P1)]})  # 继承域 D1 与 P1 一致
    exc = await reject(svc, "table", TABLE, {"domain": ref(D2)})  # 改域使既有产品不一致
    assert exc.code == "governance.domain_mismatch"
    await patch(svc, "table", TABLE, {"domain": ref(D2), "dataProducts": [ref(P2)]})


async def test_mutually_exclusive_classification_keeps_one_tag() -> None:
    _, svc = await setup()
    exc = await reject(svc, "table", TABLE, {"tags": ["PII.Sensitive", "PII.NonSensitive"]})
    assert exc.code == "governance.exclusive_tags" and exc.status_code == 400
    await patch(
        svc,
        "table",
        TABLE,
        {"tags": ["PII.Sensitive", "PersonalData.Personal", "Source.MES", "Source.ERP"]},
    )


@pytest.mark.parametrize("value", ["30 days", "P", "PT", "30D", "P1.5D"])
async def test_retention_must_be_iso8601_duration(value: str) -> None:
    _, svc = await setup()
    exc = await reject(svc, "database", DB, {"retentionPeriod": value})
    assert exc.code == "governance.invalid_retention" and exc.status_code == 400


async def test_retention_and_field_rules_per_level() -> None:
    _, svc = await setup()
    for value in ("P30D", "PT24H", "P1Y2M", "P2W", "PT1.5S"):
        await patch(svc, "database", DB, {"retentionPeriod": value})
    assert (
        await reject(svc, "databaseService", SVC, {"retentionPeriod": "P30D"})
    ).code == "governance.field_not_allowed"
    assert (
        await reject(svc, "table", TABLE, {"tier": "Tier.Tier9"})
    ).code == "governance.invalid_tier"


async def test_owners_are_users_or_a_single_team() -> None:
    _, svc = await setup()
    await patch(svc, "table", TABLE, {"owners": [ref(U1), ref(U2)]})
    await patch(svc, "table", TABLE, {"owners": [ref(T1)]})
    for owners in ([ref(U1), ref(T1)], [ref(T1), ref(T2)]):
        exc = await reject(svc, "table", TABLE, {"owners": owners})
        assert exc.code == "governance.owners_invalid" and exc.status_code == 400


async def test_column_patch_targets_column_by_name() -> None:
    om, svc = await setup()
    await patch(
        svc, "table", TABLE, {"columnName": "qty", "description": "数量", "tags": ["PII.Sensitive"]}
    )
    _, ops = om.patches[-1]
    assert {"op": "add", "path": "/columns/1/description", "value": "数量"} in ops
    t = await svc.get_catalog_entity(user_context(), "table", TABLE)
    qty = next(c for c in t["table"]["columns"] if c["name"] == "qty")
    assert (qty["description"], qty["tags"]) == ("数量", ["PII.Sensitive"])
    other = await svc.get_catalog_entity(user_context(), "table", "mock-mes.default.mes.line")
    assert all(c["description"] is None for c in other["table"]["columns"])
    assert (
        await reject(svc, "table", TABLE, {"columnName": "qty", "owners": [ref(U1)]})
    ).code == "governance.field_not_allowed"
    exc = await reject(svc, "table", TABLE, {"columnName": "nope", "description": "x"})
    assert exc.code == "catalog.column_not_found" and exc.status_code == 404
    assert (
        await reject(svc, "database", DB, {"columnName": "qty", "description": "x"})
    ).code == "governance.field_not_allowed"


async def test_governance_options_read_from_om() -> None:
    _, svc = await setup()
    o = await svc.governance_options(user_context())
    assert [u["name"] for u in o["users"]] == ["engineer1", "admin1"]  # 排除机器人
    assert [t["name"] for t in o["teams"]] == ["ai-engineer", "admin"]
    assert [d["id"] for d in o["domains"]] == [D1["id"], D2["id"]]
    assert [(p["name"], [d["id"] for d in p["domains"]]) for p in o["dataProducts"]] == [
        ("MES 工单", [D1["id"]]),
        ("质量追溯", [D2["id"]]),
    ]
    # Tier 与 Certification 在 OM 中是独立属性，不作为分类标签选项
    assert [(c["name"], c["mutuallyExclusive"], c["tags"]) for c in o["classifications"]] == [
        ("PII", True, ["PII.Sensitive", "PII.NonSensitive"]),
        ("PersonalData", True, ["PersonalData.Personal"]),
        ("Source", False, ["Source.MES", "Source.ERP"]),
    ]
    assert o["glossaryTerms"] == ["Glossary.Quantity"]
