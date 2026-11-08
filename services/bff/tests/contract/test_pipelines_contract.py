"""US2 契约：/bff/v1/sources/{name}/pipelines/{kind}/*。"""

from typing import Any

import jsonschema
from bff_fakes import user_context
from om_fake import FakeOM
from sources_helpers import upsert
from test_sources_contract import ERROR, SPEC, make


def check(body: Any, name: str) -> None:
    jsonschema.validate(body, {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]})


def test_runs_trigger_schedule_logs_match_contract() -> None:
    om = FakeOM()
    c = make(om)
    assert c.post("/bff/v1/sources", json=upsert()).status_code == 201
    base = "/bff/v1/sources/mock-mes/pipelines/metadata"
    assert c.post(f"{base}/trigger").status_code == 202
    again = c.post(f"{base}/trigger")
    assert again.status_code == 409 and again.json()["code"] == "source.pipeline_in_flight"
    jsonschema.validate(again.json(), ERROR)
    runs = c.get(f"{base}/runs")
    assert runs.status_code == 200
    for r in runs.json()["data"]:
        check(r, "PipelineRun")
    assert c.get(f"{base}/runs", params={"state": "success"}).json()["data"] == []
    sched = c.put(f"{base}/schedule", json={"enabled": False})
    assert sched.status_code == 200
    check(sched.json(), "PipelineSummary")
    logs = c.get(f"{base}/logs/last")
    assert logs.status_code == 200 and isinstance(logs.json()["logs"], str)
    assert c.get("/bff/v1/sources/mock-mes/pipelines/other/runs").status_code == 422
    assert c.get("/bff/v1/sources/mock-mes/pipelines/lineage/runs").json()["code"] == "source.not_found"


def test_manual_task_schedule_toggle_rejected() -> None:
    om = FakeOM()
    c = make(om)
    c.post("/bff/v1/sources", json=upsert(metadataSchedule={"cron": None}))
    resp = c.put("/bff/v1/sources/mock-mes/pipelines/metadata/schedule", json={"enabled": True})
    assert resp.status_code == 400 and resp.json()["code"] == "source.schedule_not_set"


_ = user_context
