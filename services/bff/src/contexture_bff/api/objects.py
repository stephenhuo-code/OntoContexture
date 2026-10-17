from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from contexture_bff.api.deps import current_context, services
from contexture_bff.api.models import ObjectInstance, ObjectListView
from contexture_core.auth import RequestContext
from contexture_core.errors import current_trace_id
from contexture_core.ontology import ObjectTypeRef

router = APIRouter(prefix="/bff/v1", tags=["objects"])

SOURCE = "mcp:list_objects"


@router.get("/object-types/{type_key}")
async def get_object_type(
    request: Request,
    type_key: str,
    ctx: Annotated[RequestContext, Depends(current_context)],
) -> ObjectTypeRef:
    """对象类型定义：OM 中已审批的对象及其属性。"""
    svc = services(request)
    assert svc.object_types is not None  # noqa: S101
    return await svc.object_types.get(type_key)


@router.get("/object-types/{type_key}/objects")
async def list_objects(
    request: Request,
    type_key: str,
    ctx: Annotated[RequestContext, Depends(current_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ObjectListView:
    """示例查询：对象定义（OM，已审批）+ 该类型的对象实例（经 AI 网关取数）。"""
    svc = services(request)
    assert svc.object_types is not None and svc.object_data is not None  # noqa: S101
    object_type = await svc.object_types.get(type_key)
    rows = await svc.object_data.list_objects(ctx, type_key=type_key, limit=limit)
    items = [
        ObjectInstance(
            # 第一列为业务主键（contracts/mcp/list_objects.yaml）
            object_uri=f"urn:ctx:obj:{ctx.tenant_id}:{object_type.name}:{row[0]}",
            type_uri=object_type.type_uri,
            attributes=dict(zip(rows.columns, row, strict=False)),
            source=SOURCE,
        )
        for row in rows.rows
    ]
    return ObjectListView(object_type=object_type, items=items, trace_id=current_trace_id())
