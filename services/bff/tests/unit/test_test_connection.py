"""测试连接（FR-003，research R6）：OM automation workflow；步骤以 OM testConnectionDefinition
为准，未执行的为 null。"""

from typing import Any

import pytest
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import service

from contexture_core.errors import ContextureError

REQ: dict[str, Any] = {
    "serviceType": "Mysql",
    "connection": {
        "hostPort": "h:3306",
        "username": "ro",
        "password": "pw",
        "database": "mes",
        "tls": False,
    },
}


async def test_successful_test_connection_lists_native_steps_and_cleans_up() -> None:
    om = FakeOM()
    svc = service(om)
    started = await svc.start_test_connection(user_context(), REQ)
    wf = om.workflows[started["workflowId"]]
    assert wf["workflowType"] == "TEST_CONNECTION"
    assert wf["request"]["connectionType"] == "Mysql" and wf["request"]["serviceType"] == "Database"
    assert wf["request"]["connection"]["config"]["authType"] == {"password": "pw"}
    result = await svc.get_test_connection(user_context(), started["workflowId"])
    assert result["status"] == "Successful"
    assert [(s["name"], s["mandatory"], s["passed"]) for s in result["steps"]] == [
        ("CheckAccess", True, True),
        ("GetSchemas", True, True),
        ("GetTables", True, True),
        ("GetViews", False, True),
        ("GetQueries", False, True),
    ]
    assert started["workflowId"] not in om.workflows  # 完成后清理


async def test_failed_check_access_shows_unexecuted_steps() -> None:
    om = FakeOM()
    om.test_connection_ok = False
    svc = service(om)
    started = await svc.start_test_connection(user_context(), REQ)
    result = await svc.get_test_connection(user_context(), started["workflowId"])
    assert result["status"] == "Failed"
    assert result["steps"][0] == {
        "name": "CheckAccess",
        "mandatory": True,
        "passed": False,
        "message": "Access denied for user",
    }
    assert all(s["passed"] is None for s in result["steps"][1:])


async def test_existing_service_passes_service_name_for_masked_password() -> None:
    om = FakeOM()
    svc = service(om)
    req = {
        **REQ,
        "serviceName": "mock-mes",
        "connection": {**REQ["connection"], "password": "*********"},
    }
    started = await svc.start_test_connection(user_context(), req)
    assert om.workflows[started["workflowId"]]["request"]["serviceName"] == "mock-mes"


async def test_om_down_raises() -> None:
    om = FakeOM()
    om.down = True
    with pytest.raises(ContextureError) as exc:
        await service(om).start_test_connection(user_context(), REQ)
    assert exc.value.code == "upstream.unavailable"


async def test_failed_optional_step_without_message_uses_om_diagnosis_or_error_log() -> None:
    """OM 2.0.3 实测：GetQueries 失败时 message 为 null，原因在 diagnosis 与 errorLog。"""
    om = FakeOM()
    om.test_steps_override = [
        {"name": n, "mandatory": m, "passed": True}
        for n, m in [
            ("CheckAccess", True),
            ("GetSchemas", True),
            ("GetTables", True),
            ("GetViews", False),
        ]
    ] + [
        {
            "name": "GetQueries",
            "mandatory": False,
            "passed": False,
            "message": None,
            "errorLog": (
                '(pymysql.err.OperationalError) (1142, "SELECT command denied") '
                "password=s3cr3t\n[SQL: ...]"
            ),
            "diagnosis": {
                "title": "Query history table not accessible",
                "remediation": "Grant SELECT on mysql.general_log",
            },
        }
    ]
    svc = service(om)
    started = await svc.start_test_connection(user_context(), REQ)
    result = await svc.get_test_connection(user_context(), started["workflowId"])
    step = result["steps"][-1]
    assert (
        step["message"] == "Query history table not accessible：Grant SELECT on mysql.general_log"
    )

    om.test_steps_override[-1].pop("diagnosis")
    started = await svc.start_test_connection(user_context(), REQ)
    step = (await svc.get_test_connection(user_context(), started["workflowId"]))["steps"][-1]
    assert step["message"].startswith("(pymysql.err.OperationalError) (1142")
    assert "s3cr3t" not in step["message"] and "[SQL" not in step["message"]
