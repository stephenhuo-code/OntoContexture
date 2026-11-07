"""管道配置与数据源保存（FR-004）：过滤规则、强制只读边界、命名、调度、部署与失败如实返回。"""

import re

import pytest
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import service, upsert

from contexture_bff.adapters.om_sources import metadata_source_config, pipeline_name
from contexture_core.errors import ContextureError


def test_filter_patterns_and_forced_read_only_boundary() -> None:
    cfg = metadata_source_config(
        {
            "databaseFilterPattern": {"includes": [], "excludes": []},
            "schemaFilterPattern": {"includes": ["^mes$"], "excludes": []},
            "tableFilterPattern": {"includes": ["^ncr.*"], "excludes": ["^tmp_"]},
            "includeViews": False,
            # 请求不能覆盖只读边界
            "markDeletedTables": True,
            "extractJsonSchema": True,
        }
    )
    assert cfg == {
        "type": "DatabaseMetadata",
        "includeViews": False,
        "markDeletedTables": False,
        "overrideMetadata": False,
        "extractJsonSchema": False,
        "includeDDL": False,
        "schemaFilterPattern": {"includes": ["^mes$"], "excludes": []},
        "tableFilterPattern": {"includes": ["^ncr.*"], "excludes": ["^tmp_"]},
    }


def test_invalid_regex_rejected_with_pattern() -> None:
    with pytest.raises(ContextureError) as exc:
        metadata_source_config({"tableFilterPattern": {"includes": ["([bad"], "excludes": []}})
    assert exc.value.code == "source.invalid_request" and exc.value.status_code == 400
    assert "([bad" in exc.value.message


def test_pipeline_name_follows_om_convention() -> None:
    name = pipeline_name("mock-mes", "metadata")
    assert re.fullmatch(r"mock_mes_metadata_[A-Za-z0-9]{8}", name)


async def test_create_saves_service_pipeline_and_deploys() -> None:
    om = FakeOM()
    detail = await service(om).create_source(user_context(), upsert())
    assert detail["connection"]["password"] == "*********"
    assert om.secrets["mock-mes"] == "secret-pw"
    [pipe] = om.pipelines.values()
    assert pipe["pipelineType"] == "metadata" and pipe["deployed"] is True
    assert pipe["airflowConfig"] == {"scheduleInterval": "0 2 * * *", "pipelineTimezone": "Asia/Shanghai"}
    assert [p["kind"] for p in detail["pipelines"]] == ["metadata"]
    assert detail["configured"] is True


async def test_manual_schedule_has_no_cron() -> None:
    om = FakeOM()
    await service(om).create_source(user_context(), upsert(metadataSchedule={"cron": None}))
    [pipe] = om.pipelines.values()
    assert pipe["airflowConfig"]["scheduleInterval"] is None


async def test_lineage_task_requires_include_views() -> None:
    with pytest.raises(ContextureError) as exc:
        await service(FakeOM()).create_source(
            user_context(), upsert(scope={"includeViews": False}, createLineageTask=True)
        )
    assert exc.value.code == "source.invalid_request"


async def test_duplicate_name_conflict() -> None:
    om = FakeOM()
    await service(om).create_source(user_context(), upsert())
    with pytest.raises(ContextureError) as exc:
        await service(om).create_source(user_context(), upsert())
    assert exc.value.code == "source.name_conflict" and exc.value.status_code == 409


async def test_deploy_failure_reported_entities_kept() -> None:
    om = FakeOM()
    om.fail_deploy = True
    with pytest.raises(ContextureError) as exc:
        await service(om).create_source(user_context(), upsert())
    assert exc.value.code == "source.deploy_failed"
    assert "Failed to deploy" in exc.value.message
    assert "mock-mes" in om.services and len(om.pipelines) == 1


async def test_update_keeps_identity_and_masked_password() -> None:
    om = FakeOM()
    svc = service(om)
    await svc.create_source(user_context(), upsert())
    body = upsert(connection={**upsert()["connection"], "password": "*********"}, metadataSchedule={"cron": None})
    detail = await svc.update_source(user_context(), "mock-mes", body)
    assert om.secrets["mock-mes"] == "secret-pw"
    assert detail["pipelines"][0]["schedule"] == {"cron": None}
    with pytest.raises(ContextureError) as exc:
        await svc.update_source(user_context(), "mock-mes", upsert(serviceType="Postgres"))
    assert exc.value.code == "source.immutable_field"
    with pytest.raises(ContextureError) as exc:
        await svc.update_source(user_context(), "mock-mes", upsert(name="other"))
    assert exc.value.code == "source.immutable_field"


async def test_list_counts_tables_and_columns_from_om() -> None:
    om = FakeOM()
    svc = service(om)
    await svc.create_source(user_context(), upsert())
    om.add_tables("mock-mes", "default", "mes", {"work_order": ["a", "b", "c"], "line": ["x"]})
    [summary] = await svc.list_sources(user_context())
    assert summary["tableCount"] == 2 and summary["columnCount"] == 4
    assert summary["pipelines"][0]["lastRun"] is None


async def test_list_empty_when_om_has_no_services() -> None:
    assert await service(FakeOM()).list_sources(user_context()) == []


async def test_om_unavailable_raises_not_sample_data() -> None:
    om = FakeOM()
    om.down = True
    with pytest.raises(ContextureError) as exc:
        await service(om).list_sources(user_context())
    assert exc.value.code == "upstream.unavailable"
