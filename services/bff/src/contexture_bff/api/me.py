from typing import Annotated

from fastapi import APIRouter, Depends

from contexture_bff.api.deps import current_context
from contexture_bff.api.models import Me
from contexture_core.auth import RequestContext

router = APIRouter(prefix="/bff/v1", tags=["me"])


@router.get("/me")
async def get_me(ctx: Annotated[RequestContext, Depends(current_context)]) -> Me:
    return Me(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id or "",
        display_name=ctx.display_name or ctx.username,
        roles=list(ctx.roles),
    )
