"""US5：视图血缘任务（OM pipelineType=lineage）的创建、独立调度、配置与删除。"""

import re

import pytest
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import service, upsert

from contexture_core.errors import ContextureError


def lineage(om: FakeOM) -> dict:  # type: ignore[type-arg]
    return next(p for p in om.pipelines.values() if p["pipelineType"] == "lineage")


async def test_lineage_pipeline_processes_view_lineage_only_with_own_schedule() -> None:
    om = FakeOM()
    detail = await service(om).create_source(
        user_context(),
        upsert(createLineageTask=True, lineageSchedule={"cron": "30 3 * * *"}),
    )
    pipe = lineage(om)
    cfg = pipe["sourceConfig"]["config"]
    assert cfg["type"] == "DatabaseLineage"
    assert (
        cfg["processViewLineage"],
        cfg["processQueryLineage"],
        cfg["processStoredProcedureLineage"],
    ) == (
        True,
        False,
        False,
    )
    assert re.fullmatch(r"mock_mes_lineage_[A-Za-z0-9]{8}", pipe["name"])
    assert pipe["airflowConfig"]["scheduleInterval"] == "30 3 * * *"
    meta = next(p for p in om.pipelines.values() if p["pipelineType"] == "metadata")
    assert meta["airflowConfig"]["scheduleInterval"] == "0 2 * * *"
    assert pipe["deployed"] is True
    assert [p["kind"] for p in detail["pipelines"]] == ["metadata", "lineage"]


async def test_lineage_requires_views_and_is_removed_when_turned_off() -> None:
    om = FakeOM()
    svc = service(om)
    with pytest.raises(ContextureError) as exc:
        await svc.create_source(
            user_context(), upsert(scope={"includeViews": False}, createLineageTask=True)
        )
    assert exc.value.code == "source.invalid_request" and exc.value.status_code == 400
    await svc.create_source(
        user_context(), upsert(createLineageTask=True, lineageSchedule={"cron": None})
    )
    lineage_id = lineage(om)["id"]
    detail = await svc.update_source(user_context(), "mock-mes", upsert(createLineageTask=False))
    assert [p["kind"] for p in detail["pipelines"]] == ["metadata"]
    assert lineage_id not in om.pipelines
    assert ("DELETE", f"/services/ingestionPipelines/{lineage_id}") in om.calls


async def test_lineage_task_keeps_name_when_reconfigured() -> None:
    om = FakeOM()
    svc = service(om)
    await svc.create_source(
        user_context(), upsert(createLineageTask=True, lineageSchedule={"cron": None})
    )
    name = lineage(om)["name"]
    await svc.update_source(
        user_context(),
        "mock-mes",
        upsert(createLineageTask=True, lineageSchedule={"cron": "0 4 * * *"}),
    )
    assert lineage(om)["name"] == name
    assert lineage(om)["airflowConfig"]["scheduleInterval"] == "0 4 * * *"
