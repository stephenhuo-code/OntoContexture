"""/bff/v1/sources*（005）：仅 admin / ai-engineer；写操作留存审计（FR-010）。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from contexture_bff.adapters.om_sources import SourcesService
from contexture_bff.api.deps import require_web_context, services
from contexture_bff.audit import audit_write
from contexture_core.auth import RequestContext
from contexture_core.errors import UpstreamUnavailable

from starlette.convertors import Convertor, register_url_convertor  # noqa: E402


class SourceNameConvertor(Convertor[str]):
    """服务标识；排除保留名 test-connection，避免与测试连接接口冲突。"""

    regex = r"(?!test-connection(?:/|$))[a-z][a-z0-9-]{1,49}"

    def convert(self, value: str) -> str:
        return value

    def to_string(self, value: str) -> str:
        return value


register_url_convertor("source_name", SourceNameConvertor())
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


# ---------- 请求模型（contracts/openapi/bff.yaml：SourceUpsert、ConnectionInput、Scope） ----------
from typing import Literal  # noqa: E402

from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

ServiceType = Literal["Mysql", "Postgres", "Oracle", "Mssql", "Doris"]


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    hostPort: str = Field(min_length=1)  # noqa: N815
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    database: str | None = None
    tls: bool = False


class FilterPattern(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    includes: list[str] = []
    excludes: list[str] = []


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    databaseFilterPattern: FilterPattern | None = None  # noqa: N815
    schemaFilterPattern: FilterPattern | None = None  # noqa: N815
    tableFilterPattern: FilterPattern | None = None  # noqa: N815
    includeViews: bool = True  # noqa: N815


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    cron: str | None = None


class SourceUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,49}$")
    displayName: str = Field(min_length=1, max_length=60)  # noqa: N815
    serviceType: ServiceType  # noqa: N815
    connection: ConnectionInput
    scope: Scope
    metadataSchedule: Schedule  # noqa: N815
    createLineageTask: bool = False  # noqa: N815
    lineageSchedule: Schedule | None = None  # noqa: N815


class TestConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    serviceName: str | None = None  # noqa: N815
    serviceType: ServiceType  # noqa: N815
    connection: ConnectionInput


# ---------- 路由 ----------
from fastapi import Path, status  # noqa: E402

Name = Annotated[str, Path()]


@router.get("/sources")
async def list_sources(ctx: WebContext, svc: Sources) -> dict[str, Any]:
    return {"data": await svc.list_sources(ctx)}


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def create_source(request: Request, body: SourceUpsert, ctx: WebContext, svc: Sources) -> dict[str, Any]:
    audited(request, ctx)
    return await svc.create_source(ctx, body.model_dump())


@router.post("/sources/test-connection", status_code=status.HTTP_202_ACCEPTED)
async def start_test_connection(
    request: Request, body: TestConnectionRequest, ctx: WebContext, svc: Sources
) -> dict[str, Any]:
    audited(request, ctx)
    return await svc.start_test_connection(ctx, body.model_dump())


@router.get("/sources/test-connection/{workflowId}")
async def get_test_connection(
    workflowId: Annotated[str, Path(pattern=r"^[0-9a-fA-F-]{36}$")],  # noqa: N803
    ctx: WebContext,
    svc: Sources,
) -> dict[str, Any]:
    return await svc.get_test_connection(ctx, workflowId)


@router.get("/sources/{name:source_name}")
async def get_source(name: Name, ctx: WebContext, svc: Sources) -> dict[str, Any]:
    return await svc.get_source(ctx, name)


@router.put("/sources/{name:source_name}")
async def update_source(
    request: Request, name: Name, body: SourceUpsert, ctx: WebContext, svc: Sources
) -> dict[str, Any]:
    audited(request, ctx)
    return await svc.update_source(ctx, name, body.model_dump())

