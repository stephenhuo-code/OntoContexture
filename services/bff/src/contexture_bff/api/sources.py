"""/bff/v1/sources*（005）：仅 admin / ai-engineer；写操作留存审计（FR-010）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from contexture_bff.adapters.om_sources import SourcesService
from contexture_bff.api.deps import require_web_context, services
from contexture_bff.audit import audit_write
from contexture_core.auth import RequestContext
from contexture_core.errors import UpstreamUnavailable

router = APIRouter(prefix="/bff/v1")
WebContext = Annotated[RequestContext, Depends(require_web_context)]


def sources_service(request: Request) -> SourcesService:
    svc = services(request).sources
    if svc is None:
        raise UpstreamUnavailable("数据源服务未配置", details={"upstream": "openmetadata"})
    return svc


Sources = Annotated[SourcesService, Depends(sources_service)]


def audited(request: Request, ctx: RequestContext) -> None:
    audit_write(ctx, method=request.method, path=request.url.path)
