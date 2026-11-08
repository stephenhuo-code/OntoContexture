"""写操作审计（FR-010）：结构化日志含 trace_id、tenant_id、user_id，action=write、resource=api +
方法与实际路径。"""

import json
import logging

import pytest
from bff_fakes import user_context

from contexture_bff.audit import AUDIT_LOGGER, audit_write


def test_audit_write_logs_structured_event(caplog: pytest.LogCaptureFixture) -> None:
    ctx = user_context(roles=("admin",))
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER):
        audit_write(ctx, method="POST", path="/bff/v1/sources/mock-mes/pipelines/metadata/trigger")
    records = [r for r in caplog.records if r.name == AUDIT_LOGGER]
    assert len(records) == 1
    event = json.loads(records[0].getMessage())
    assert event["action"] == "write"
    assert event["resource"] == {
        "kind": "api",
        "ref": "POST /bff/v1/sources/mock-mes/pipelines/metadata/trigger",
    }
    assert event["tenant_id"] == "local"
    assert event["user_id"] == "user-1-id"
    assert event["agent_id"] == "contexture-bff"
    assert event["token_id"] == "jti-1"
    assert len(event["trace_id"]) == 32
    assert event["source_service"] == "bff"
    assert "access-token" not in records[0].getMessage()
