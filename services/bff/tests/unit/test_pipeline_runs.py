"""US2：运行记录（PipelineStatus 原样投影）、在途防重入、暂停 / 恢复（toggleIngestion）、最近日志。"""

import pytest
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import service, upsert

from contexture_core.errors import ContextureError


async def created(om: FakeOM, **kw: object):  # type: ignore[no-untyped-def]
    svc = service(om)
    await svc.create_source(user_context(), upsert(**kw))
    return svc


async def test_runs_are_projected_new_to_old_without_trigger_type() -> None:
    om = FakeOM()
    svc = await created(om)
    fqn = next(iter(om.pipelines.values()))["fullyQualifiedName"]
    old = om.add_run(fqn, "partialSuccess", 1_000, 2_000)
    new = om.add_run(fqn, "success", 5_000, 9_000)
    runs = await svc.list_runs(user_context(), "mock-mes", "metadata")
    assert [r["runId"] for r in runs] == [new, old]
    assert runs[0]["steps"][0] == {
        "name": "Mysql", "records": 15, "updatedRecords": 0, "warnings": 0, "errors": 0, "filtered": 0, "failures": [],
    }
    assert "trigger" not in runs[0] and "triggerType" not in runs[0]
    partial = await svc.list_runs(user_context(), "mock-mes", "metadata", state="partialSuccess")
    assert [r["runId"] for r in partial] == [old]


async def test_trigger_rejected_while_in_flight_and_other_task_unaffected() -> None:
    om = FakeOM()
    svc = await created(om, createLineageTask=True, lineageSchedule={"cron": None})
    await svc.trigger(user_context(), "mock-mes", "metadata")
    with pytest.raises(ContextureError) as exc:
        await svc.trigger(user_context(), "mock-mes", "metadata")
    assert exc.value.code == "source.pipeline_in_flight" and exc.value.status_code == 409
    await svc.trigger(user_context(), "mock-mes", "lineage")  # 另一条任务不受影响


async def test_schedule_toggle_uses_om_toggle_and_requires_cron() -> None:
    om = FakeOM()
    svc = await created(om)
    view = await svc.set_schedule(user_context(), "mock-mes", "metadata", enabled=False)
    assert view["scheduleEnabled"] is False
    assert ("POST", f"/services/ingestionPipelines/toggleIngestion/{next(iter(om.pipelines))}") in om.calls
    same = await svc.set_schedule(user_context(), "mock-mes", "metadata", enabled=False)
    assert same["scheduleEnabled"] is False
    assert sum(1 for c in om.calls if "toggleIngestion" in c[1]) == 1  # 已是目标状态不重复切换
    manual = FakeOM()
    svc2 = await created(manual, metadataSchedule={"cron": None})
    with pytest.raises(ContextureError) as exc:
        await svc2.set_schedule(user_context(), "mock-mes", "metadata", enabled=False)
    assert exc.value.code == "source.schedule_not_set"


async def test_last_logs_are_redacted() -> None:
    om = FakeOM()
    svc = await created(om)
    fqn = next(iter(om.pipelines.values()))["fullyQualifiedName"]
    run = om.add_run(fqn, "success", 1, 2)
    logs = await svc.last_logs(user_context(), "mock-mes", "metadata")
    assert logs["runId"] == run
    assert "采集完成" in logs["logs"]


def test_redact_hides_password_like_values() -> None:
    from contexture_bff.adapters.om_sources import redact

    text = "connect password=s3cr3t token: abc 'password': 'x1'"
    out = redact(text)
    assert "s3cr3t" not in out and "abc" not in out and "x1" not in out


async def test_unknown_task_is_not_found() -> None:
    om = FakeOM()
    svc = await created(om)
    with pytest.raises(ContextureError) as exc:
        await svc.list_runs(user_context(), "mock-mes", "lineage")
    assert exc.value.code == "source.not_found"
