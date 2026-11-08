"""/bff/v1/catalog/{entityType}/{fqn} 与 /bff/v1/governance/options（005 US3 / US4）：实时读写 OpenMetadata。"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from contexture_bff.api.sources import Sources, WebContext, audited

router = APIRouter(prefix="/bff/v1")
EntityType = Annotated[Literal["databaseService", "database", "databaseSchema", "table"], Path()]
Fqn = Annotated[str, Path(min_length=1)]
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class Ref(BaseModel):
    """contracts/openapi/bff.yaml：Ref"""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=UUID_PATTERN)
    type: str = Field(min_length=1)
    name: str | None = None
    displayName: str | None = None  # noqa: N815
    fullyQualifiedName: str | None = None  # noqa: N815


class GovernancePatch(BaseModel):
    """contracts/openapi/bff.yaml：GovernancePatch；未出现的字段不修改，null 表示清空（恢复继承）。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    columnName: str | None = Field(default=None, min_length=1)  # noqa: N815
    displayName: str | None = None  # noqa: N815
    description: str | None = None
    owners: list[Ref] | None = None
    domain: Ref | None = None
    tier: str | None = None
    tags: list[str] | None = None
    glossaryTerms: list[str] | None = None  # noqa: N815
    dataProducts: list[Ref] | None = None  # noqa: N815
    retentionPeriod: str | None = None  # noqa: N815


@router.get("/catalog/{entityType}/{fqn}")
async def get_catalog_entity(
    entityType: EntityType,  # noqa: N803
    fqn: Fqn,
    ctx: WebContext,
    svc: Sources,
) -> dict[str, Any]:
    return await svc.get_catalog_entity(ctx, entityType, fqn)


@router.patch("/catalog/{entityType}/{fqn}")
async def patch_catalog_entity(
    request: Request,
    entityType: EntityType,  # noqa: N803
    fqn: Fqn,
    body: GovernancePatch,
    ctx: WebContext,
    svc: Sources,
) -> dict[str, Any]:
    audited(request, ctx)
    changes = body.model_dump(exclude_unset=True)
    return await svc.patch_catalog_entity(ctx, entityType, fqn, changes)


@router.get("/governance/options")
async def governance_options(ctx: WebContext, svc: Sources) -> dict[str, Any]:
    return await svc.governance_options(ctx)
