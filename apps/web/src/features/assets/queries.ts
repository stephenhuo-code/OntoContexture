// 006 资产搜索的共享读取（React Query）：与 005 相同的选项——不自动重试、不在聚焦时刷新、不使用过期缓存。
import { useQuery } from "@tanstack/react-query";
import type {
  BrowseStep,
  EntityType,
  FacetDimension,
  SearchCriteria,
} from "@contexture/ts-api";
import { asApiError, type Load } from "../sources/useLoad";
import {
  assetFacet,
  assetSummary,
  browseAssets,
  countAssetTypes,
  searchAssets,
  suggestAssets,
} from "./api";
import { initialCriteria, toRequest, type Criteria } from "./criteria";

export const ASSETS_KEY = ["assets"] as const;
const options = {
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: 0,
} as const;

export function toLoad<T>(q: {
  data?: T;
  error: unknown;
  isPending: boolean;
  isError: boolean;
  isFetching?: boolean;
}): Load<T> {
  if (q.isError) return { status: "error", error: asApiError(q.error) };
  if (q.isPending) return { status: "loading" };
  return { status: "ready", data: q.data as T };
}

export function useTypeCounts(criteria: Criteria, enabled = true) {
  const body = {
    ...toRequest(criteria),
    entityType: null,
    scope: null,
    page: 1,
  };
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "type-counts", body],
    queryFn: ({ signal }) => countAssetTypes(body, signal),
    enabled,
    ...options,
  });
  return { state: toLoad(q), reload: () => void q.refetch() };
}

/** 搜索范围的选项：当前有数据的类型（keyword 为空时的按类型计数，FR-004） */
export function useScopeOptions() {
  const body: SearchCriteria = toRequest(initialCriteria);
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "scope-options"],
    queryFn: ({ signal }) => countAssetTypes(body, signal),
    ...options,
  });
  return q.data?.counts.map((c) => c.entityType) ?? [];
}

export function useSearch(body: SearchCriteria | null) {
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "search", body],
    queryFn: ({ signal }) => searchAssets(body as SearchCriteria, signal),
    enabled: body !== null,
    ...options,
  });
  return {
    state: toLoad(q),
    fetching: q.isFetching,
    reload: () => void q.refetch(),
  };
}

export function useSuggestions(keyword: string, scope: EntityType | null) {
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "suggest", keyword, scope],
    queryFn: ({ signal }) => suggestAssets(keyword, scope, signal),
    enabled: keyword.length > 0,
    ...options,
  });
  return toLoad(q);
}

export function useSummary(type: EntityType, fqn: string) {
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "summary", type, fqn],
    queryFn: () => assetSummary(type, fqn),
    ...options,
  });
  return { state: toLoad(q), reload: () => void q.refetch() };
}

/** 浏览树的一层：计数受筛选条件约束；位置、排序与分页不影响计数，缓存键中去掉 */
export function useBrowse(
  criteria: Criteria,
  parentPath: BrowseStep[],
  enabled = true,
) {
  const body = {
    ...toRequest({ ...initialCriteria, filters: criteria.filters }),
  };
  const path = parentPath.map(({ level, value }) => ({ level, value }));
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "browse", body, path],
    queryFn: () => browseAssets(body, path),
    enabled,
    ...options,
  });
  return { state: toLoad(q), reload: () => void q.refetch() };
}

export function useFacet(
  request: SearchCriteria,
  dimension: FacetDimension,
  optionQuery: string,
  enabled: boolean,
) {
  const body = { ...request, page: 1, pageSize: 15 as const };
  const q = useQuery({
    queryKey: [...ASSETS_KEY, "facet", body, dimension, optionQuery],
    queryFn: () => assetFacet(body, dimension, optionQuery || undefined),
    enabled,
    ...options,
  });
  return { state: toLoad(q), reload: () => void q.refetch() };
}
