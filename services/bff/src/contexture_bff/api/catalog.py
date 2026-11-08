"""/bff/v1/catalog/{entityType}/{fqn}（005 US3）：四层目录实体，实时读取 OpenMetadata。"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path

from contexture_bff.api.sources import Sources, WebContext

router = APIRouter(prefix="/bff/v1")
EntityType = Annotated[Literal["databaseService", "database", "databaseSchema", "table"], Path()]


@router.get("/catalog/{entityType}/{fqn}")
async def get_catalog_entity(
    entityType: EntityType,  # noqa: N803
    fqn: Annotated[str, Path(min_length=1)],
    ctx: WebContext,
    svc: Sources,
) -> dict[str, Any]:
    return await svc.get_catalog_entity(ctx, entityType, fqn)
