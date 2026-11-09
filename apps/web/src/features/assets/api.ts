// 006 资产搜索与摘要接口封装：一律经 BFF（契约 contracts/openapi/bff.yaml）。
// 宪法 v2.2.0：错误原样抛出（含错误码与 trace_id），不得捕获后返回示例数据或伪造成功。
import type {
  AssetSummary,
  BrowseNode,
  BrowseStep,
  EntityType,
  FacetDimension,
  FacetOption,
  GlossaryTermDetail,
  SearchCriteria,
  SearchPage,
  Suggestion,
  TagDetail,
  TypeCounts,
} from "@contexture/ts-api";
import { ApiFailure, bff, toApiError } from "../../api";

type Call = Promise<{ data?: unknown; error?: unknown; response: Response }>;

async function unwrap<T>(call: Call): Promise<T> {
  let result: Awaited<Call>;
  try {
    result = await call;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiFailure(0);
  }
  const { data, error, response } = result;
  if (response.status !== 200)
    throw new ApiFailure(response.status, toApiError(error, response.status));
  return data as T;
}

/** 响应结构不符视为服务端错误（500），不猜测、不回退示例数据 */
function shaped<T>(data: T, ok: (d: T) => boolean): T {
  if (!data || typeof data !== "object" || !ok(data)) throw new ApiFailure(500);
  return data;
}

export const searchAssets = async (
  body: SearchCriteria,
  signal?: AbortSignal,
) =>
  shaped(
    await unwrap<SearchPage>(
      bff.POST("/bff/v1/assets/search", { body, signal }),
    ),
    (d) => Array.isArray(d.hits) && typeof d.total === "number",
  );

export const countAssetTypes = async (
  body: SearchCriteria,
  signal?: AbortSignal,
) =>
  shaped(
    await unwrap<TypeCounts>(
      bff.POST("/bff/v1/assets/type-counts", { body, signal }),
    ),
    (d) => Array.isArray(d.counts),
  );

export const suggestAssets = async (
  keyword: string,
  scope: EntityType | null,
  signal?: AbortSignal,
) =>
  shaped(
    await unwrap<{ groups: { entityType: EntityType; items: Suggestion[] }[] }>(
      bff.GET("/bff/v1/assets/suggestions", {
        params: { query: scope ? { keyword, scope } : { keyword } },
        signal,
      }),
    ),
    (d) => Array.isArray(d.groups),
  );

export const assetSummary = async (type: EntityType, fqn: string) =>
  shaped(
    await unwrap<AssetSummary>(
      bff.GET("/bff/v1/assets/summary/{entityType}/{fqn}", {
        params: { path: { entityType: type, fqn } },
      }),
    ),
    (d) => !!d.ref && typeof d.governance === "object",
  );

export const assetFacet = (
  criteria: SearchCriteria,
  dimension: FacetDimension,
  optionQuery?: string,
) =>
  unwrap<{
    dimension: FacetDimension;
    supportsNone?: boolean;
    options: FacetOption[];
  }>(
    bff.POST("/bff/v1/assets/facets", {
      body: optionQuery
        ? { criteria, dimension, optionQuery }
        : { criteria, dimension },
    }),
  );

export const browseAssets = (
  criteria: SearchCriteria,
  parentPath: BrowseStep[],
) =>
  unwrap<{ nodes: BrowseNode[] }>(
    bff.POST("/bff/v1/assets/browse", { body: { criteria, parentPath } }),
  );

export const glossaryTermDetail = (fqn: string) =>
  unwrap<GlossaryTermDetail>(
    bff.GET("/bff/v1/governance/glossary-terms/{fqn}", {
      params: { path: { fqn } },
    }),
  );

export const tagDetail = (fqn: string) =>
  unwrap<TagDetail>(
    bff.GET("/bff/v1/governance/tags/{fqn}", { params: { path: { fqn } } }),
  );
