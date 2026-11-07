"""写操作审计（FR-010，宪法 IV）：结构化 JSON 日志，符合 contracts/schemas/audit-event.json。

005 的写操作记 action=write、resource.kind=api、resource.ref=“<方法> <实际请求路径>”（路径即包含目标；
schema 无其他可放目标的字段且 additionalProperties=false）。日志经 OTel Collector 进入可观测体系。
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from contexture_core.auth import RequestContext

AUDIT_LOGGER = "contexture_bff.audit"
_logger = logging.getLogger(AUDIT_LOGGER)


def build_audit_event(ctx: RequestContext, *, method: str, path: str) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "tenant_id": ctx.tenant_id,
        "user_id": ctx.user_id,
        "agent_id": ctx.agent_id,
        "token_id": ctx.token_id,
        "action": "write",
        "resource": {"kind": "api", "ref": f"{method} {path}"},
        "trace_id": ctx.trace_id,
        "source_service": "bff",
    }


def audit_write(ctx: RequestContext, *, method: str, path: str) -> None:
    _logger.info(json.dumps(build_audit_event(ctx, method=method, path=path), ensure_ascii=False))
