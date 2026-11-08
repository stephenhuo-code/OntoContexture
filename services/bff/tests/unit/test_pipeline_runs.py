"""US2：运行记录（PipelineStatus 原样投影）、在途防重入、暂停 / 恢复（toggleIngestion）、
最近日志。"""

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
        "name": "Mysql",
        "records": 15,
        "updatedRecords": 0,
        "warnings": 0,
        "errors": 0,
        "filtered": 0,
        "failures": [],
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
    assert (
        "POST",
        f"/services/ingestionPipelines/toggleIngestion/{next(iter(om.pipelines))}",
    ) in om.calls
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


async def test_trigger_waits_for_dag_settle_after_recent_deploy() -> None:
    """Airflow 3 下部署后立即触发会产生“无任务即成功”的空运行（2026-11-08 实测 2/4），
    触发前等待部署满 settle 秒。"""
    import time

    om = FakeOM()
    svc = service(om)
    svc.settle_seconds = 0.3
    await svc.create_source(user_context(), upsert())
    started = time.monotonic()
    await svc.trigger(user_context(), "mock-mes", "metadata")
    assert time.monotonic() - started >= 0.25
    svc.settle_seconds = 0.0
    fqn = next(iter(om.pipelines.values()))["fullyQualifiedName"]
    om.statuses[fqn][0]["pipelineState"] = "success"
    started = time.monotonic()
    await svc.trigger(user_context(), "mock-mes", "metadata")
    assert time.monotonic() - started < 0.2


async def test_wait_for_run_ignores_the_previous_run() -> None:
    """触发后新运行登记前，最近一条仍是上一次运行；指定 after_run_id 时须等到新运行结束。"""
    om = FakeOM()
    svc = await created(om)
    fqn = next(iter(om.pipelines.values()))["fullyQualifiedName"]
    old = om.add_run(fqn, "success", 1_000, 2_000)
    with pytest.raises(ContextureError) as exc:
        await svc.wait_for_run(user_context(), "mock-mes", "metadata", timeout=0, after_run_id=old)
    assert exc.value.code == "source.run_timeout"
    new = om.add_run(fqn, "success", 5_000, 9_000)
    run = await svc.wait_for_run(
        user_context(), "mock-mes", "metadata", timeout=0, after_run_id=old
    )
    assert run["runId"] == new
