"""/bff/v1/assets/*（006）：资产搜索、类型计数、输入建议与只读摘要；仅 admin / ai-engineer。

浏览器只提交结构化条件（SearchCriteria），由 BFF 生成并校验 OM 查询（FR-019）；全部为只读接口。
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from contexture_bff.adapters.om_assets import AssetReader
from contexture_bff.adapters.om_search import SearchService
from contexture_bff.api.deps import services
from contexture_bff.api.sources import WebContext
from contexture_core.errors import UpstreamUnavailable

router = APIRouter(prefix="/bff/v1")


def search_service(request: Request) -> SearchService:
    svc = services(request).assets
    if svc is None:
        raise UpstreamUnavailable("资产搜索服务未配置", details={"upstream": "openmetadata"})
    return svc


def asset_reader(request: Request) -> AssetReader:
    svc = services(request).asset_reader
    if svc is None:
        raise UpstreamUnavailable("资产读取服务未配置", details={"upstream": "openmetadata"})
    return svc


Search = Annotated[SearchService, Depends(search_service)]
Reader = Annotated[AssetReader, Depends(asset_reader)]

# ---------- 请求模型（contracts/openapi/bff.yaml：SearchCriteria 等）
# 结构不符时 422 request.invalid；
# 语义校验（类型白名单组合、仅表类型维度、结果窗口）由 om_search.parse_criteria 返回 search.* 错误码
EntityType = Literal[
    "table", "tableColumn", "storedProcedure", "databaseSchema", "database", "chart", "dashboard",
    "dashboardDataModel", "pipeline", "topic", "container", "directory", "file", "spreadsheet",
    "worksheet", "searchIndex", "mlmodel", "dataProduct", "metric", "glossaryTerm", "tag",
    "apiCollection", "apiEndpoint", "page",
]  # fmt: skip
FacetDimension = Literal[
    "entityType", "domain", "dataProduct", "owner", "tag", "tier", "service", "serviceType",
    "certification", "database", "databaseSchema", "column", "tableType", "columnDescriptionStatus",
]  # fmt: skip
Level = Literal["root", "serviceType", "service", "database", "databaseSchema", "entityType"]
Strict = ConfigDict(extra="forbid", strict=True)


class BrowseStepModel(BaseModel):
    model_config = Strict
    level: Level
    value: str = Field(min_length=1, max_length=256)
    label: str = ""  # 只用于在条件条上显示；契约中为字符串，不接受 null


class FilterValueModel(BaseModel):
    model_config = Strict
    values: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(
        default_factory=list, max_length=50
    )
    includeNone: bool = False  # noqa: N815


class SortModel(BaseModel):
    model_config = Strict
    field: Literal["popularity", "name", "relevance", "updatedAt"] = "popularity"
    order: Literal["asc", "desc"] = "desc"


class SearchCriteriaModel(BaseModel):
    model_config = Strict
    keyword: str = Field(default="", max_length=200)
    scope: EntityType | None = None
    entityType: EntityType | None = None  # noqa: N815
    browsePath: list[BrowseStepModel] = Field(default_factory=list, max_length=6)  # noqa: N815
    filters: dict[FacetDimension, FilterValueModel] = Field(default_factory=dict)
    sort: SortModel = Field(default_factory=SortModel)
    page: int = Field(default=1, ge=1)
    pageSize: Literal[15, 25, 50] = 15  # noqa: N815


class FacetRequest(BaseModel):
    model_config = Strict
    criteria: SearchCriteriaModel
    dimension: FacetDimension
    optionQuery: str = Field(default="", max_length=100)  # noqa: N815


class BrowseRequest(BaseModel):
    model_config = Strict
    criteria: SearchCriteriaModel
    parentPath: list[BrowseStepModel] = Field(max_length=5)  # noqa: N815


def raw(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


@router.post("/assets/search")
async def search_assets(body: SearchCriteriaModel, ctx: WebContext, svc: Search) -> dict[str, Any]:
    return await svc.search(ctx, raw(body))


@router.post("/assets/type-counts")
async def count_asset_types(
    body: SearchCriteriaModel, ctx: WebContext, svc: Search
) -> dict[str, Any]:
    return await svc.type_counts(ctx, raw(body))


@router.post("/assets/facets")
async def get_asset_facet(body: FacetRequest, ctx: WebContext, svc: Search) -> dict[str, Any]:
    return await svc.facets(ctx, raw(body.criteria), body.dimension, body.optionQuery)


@router.post("/assets/browse")
async def browse_assets(body: BrowseRequest, ctx: WebContext, svc: Search) -> dict[str, Any]:
    return await svc.browse(ctx, raw(body.criteria), [raw(s) for s in body.parentPath])


@router.get("/assets/suggestions")
async def suggest_assets(
    ctx: WebContext,
    svc: Search,
    keyword: Annotated[str, Query(min_length=1, max_length=200)],
    scope: Annotated[EntityType | None, Query()] = None,
) -> dict[str, Any]:
    return await svc.suggestions(ctx, keyword, scope)


@router.get("/assets/summary/{entityType}/{fqn}")
async def get_asset_summary(
    entityType: Annotated[EntityType, Path()],  # noqa: N803
    fqn: Annotated[str, Path(min_length=1)],
    ctx: WebContext,
    svc: Reader,
) -> dict[str, Any]:
    return await svc.summary(ctx, entityType, fqn)
