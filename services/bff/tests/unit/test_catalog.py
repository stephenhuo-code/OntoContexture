"""US3：四层目录（服务 → 数据库 → Schema → 表）按 OM 实体层级读取；表的类型、约束与字段只读展示，不伪造。"""

import pytest
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import service, upsert

from contexture_core.errors import ContextureError


async def catalog() -> tuple[FakeOM, object]:
    om = FakeOM()
    svc = service(om)
    await svc.create_source(user_context(), upsert())
    om.add_tables(
        "mock-mes", "default", "mes",
        {"work_order": [("wo_no", "varchar(20)", "PRIMARY_KEY"), ("qty", "int", None)], "line": ["code"]},
        constraints={"work_order": [{"constraintType": "PRIMARY_KEY", "columns": ["wo_no"]}]},
    )
    om.add_tables("mock-mes", "default", "mes", {"v_report": ["wo_no"]}, table_type="View")
    return om, svc


async def test_service_lists_databases_with_child_counts() -> None:
    _, svc = await catalog()
    e = await svc.get_catalog_entity(user_context(), "databaseService", "mock-mes")
    assert e["entityType"] == "databaseService" and e["fullyQualifiedName"] == "mock-mes"
    assert e["children"] == [
        {"entityType": "database", "name": "default", "fullyQualifiedName": "mock-mes.default",
         "displayName": None, "description": None, "childCount": 1}
    ]


async def test_database_and_schema_children() -> None:
    _, svc = await catalog()
    db = await svc.get_catalog_entity(user_context(), "database", "mock-mes.default")
    assert db["children"] == [
        {"entityType": "databaseSchema", "name": "mes", "fullyQualifiedName": "mock-mes.default.mes",
         "displayName": None, "description": None, "childCount": 3}
    ]
    schema = await svc.get_catalog_entity(user_context(), "databaseSchema", "mock-mes.default.mes")
    assert {c["name"]: c["childCount"] for c in schema["children"]} == {"work_order": 2, "line": 1, "v_report": 1}


async def test_table_structure_is_read_only_projection() -> None:
    _, svc = await catalog()
    t = await svc.get_catalog_entity(user_context(), "table", "mock-mes.default.mes.work_order")
    assert t["table"]["tableType"] == "Regular"
    assert t["table"]["constraints"] == [{"constraintType": "PRIMARY_KEY", "columns": ["wo_no"]}]
    assert [(c["name"], c["dataTypeDisplay"], c["constraint"]) for c in t["table"]["columns"]] == [
        ("wo_no", "varchar(20)", "PRIMARY_KEY"), ("qty", "int", None),
    ]
    view = await svc.get_catalog_entity(user_context(), "table", "mock-mes.default.mes.v_report")
    assert view["table"]["tableType"] == "View" and view["table"]["constraints"] == []


async def test_unknown_entity_not_found() -> None:
    _, svc = await catalog()
    with pytest.raises(ContextureError) as exc:
        await svc.get_catalog_entity(user_context(), "table", "mock-mes.default.mes.nope")
    assert exc.value.code == "catalog.not_found" and exc.value.status_code == 404
