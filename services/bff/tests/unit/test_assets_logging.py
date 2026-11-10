"""006 FR-020：每次搜索、摘要与详情请求输出一条结构化日志；不记关键词原文与令牌。"""

import json
import logging
from typing import Any

import pytest
from assets_helpers import TABLE_FQN, seed
from contract_helpers import make
from om_fake import FakeOM

from contexture_bff.api.assets import ASSETS_LOGGER

CALLS = [
    (
        "POST",
        "/bff/v1/assets/search",
        {"keyword": "机密工单", "filters": {"tier": {"values": ["tier.tier1"]}}},
        "search",
    ),
    ("POST", "/bff/v1/assets/type-counts", {"keyword": "机密工单"}, "type-counts"),
    ("POST", "/bff/v1/assets/facets", {"criteria": {}, "dimension": "owner"}, "facets"),
    ("POST", "/bff/v1/assets/browse", {"criteria": {}, "parentPath": []}, "browse"),
    ("GET", "/bff/v1/assets/suggestions?keyword=机密工单", None, "suggestions"),
    ("GET", f"/bff/v1/assets/summary/table/{TABLE_FQN}", None, "summary"),
    ("GET", "/bff/v1/governance/glossary-terms/ContextureDevGlossary.工单", None, "glossary-term"),
    ("GET", "/bff/v1/governance/tags/数据级别.一级", None, "tag"),
]


@pytest.mark.parametrize("method,path,body,operation", CALLS, ids=[c[3] for c in CALLS])
def test_one_structured_log_per_request(
    caplog: pytest.LogCaptureFixture,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    operation: str,
) -> None:
    om = FakeOM()
    seed(om)
    c = make(om)
    with caplog.at_level(logging.INFO, logger=ASSETS_LOGGER):
        r = c.request(method, path, json=body)
    assert r.status_code == 200, r.text
    records = [x for x in caplog.records if x.name == ASSETS_LOGGER]
    assert len(records) == 1
    event = json.loads(records[0].getMessage())
    assert event["operation"] == operation
    assert event["tenant_id"] == "local"
    assert len(event["trace_id"]) == 32
    assert event["user_id"] == "user-1-id"
    assert isinstance(event["duration_ms"], int)
    assert "outcome" in event and event["outcome"] == "ok"
    message = records[0].getMessage()
    assert "机密工单" not in message and "access-token" not in message
    if operation == "search":
        assert event["keyword_length"] == 4
        assert event["dimensions"] == ["tier"]
        assert isinstance(event["result_count"], int)


def test_failure_is_logged_with_error_code(caplog: pytest.LogCaptureFixture) -> None:
    om = FakeOM()
    om.connect_error = True
    c = make(om)
    with caplog.at_level(logging.INFO, logger=ASSETS_LOGGER):
        r = c.post("/bff/v1/assets/search", json={})
    assert r.status_code == 502
    event = json.loads(next(x for x in caplog.records if x.name == ASSETS_LOGGER).getMessage())
    assert (event["outcome"], event["error_code"]) == ("error", "upstream.unavailable")
