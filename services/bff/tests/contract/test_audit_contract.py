"""契约测试：005 写操作的审计事件符合 contracts/schemas/audit-event.json（不改 schema）。"""

import json
from pathlib import Path

import jsonschema
import pytest
from bff_fakes import user_context

from contexture_bff.audit import build_audit_event

CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"
SCHEMA = json.loads((CONTRACTS / "schemas" / "audit-event.json").read_text())


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/bff/v1/sources"),
        ("PUT", "/bff/v1/sources/mock-mes"),
        ("POST", "/bff/v1/sources/test-connection"),
        ("POST", "/bff/v1/sources/mock-mes/pipelines/metadata/trigger"),
        ("PUT", "/bff/v1/sources/mock-mes/pipelines/lineage/schedule"),
        ("PATCH", "/bff/v1/catalog/table/mock-mes.default.mes.work_order"),
    ],
)
def test_write_audit_event_matches_schema(method: str, path: str) -> None:
    ctx = user_context(roles=("admin",))
    event = build_audit_event(ctx, method=method, path=path)
    jsonschema.validate(event, SCHEMA)
    assert event["action"] == "write"
    assert event["resource"] == {"kind": "api", "ref": f"{method} {path}"}
    assert event["tenant_id"] == ctx.tenant_id
    assert event["user_id"] == ctx.user_id
    assert event["trace_id"]
    assert event["source_service"] == "bff"
