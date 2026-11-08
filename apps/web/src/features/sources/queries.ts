// 005 数据源与目录的共享读取（React Query 缓存）：列表、目录树与详情共用同一份数据，
// 运行结束、保存配置、编辑属性后统一失效，所有使用处自动重新读取（负责人 2026-11-08 确认）。
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type {
  CatalogEntity,
  CatalogEntityType,
  SourceSummary,
} from "@contexture/ts-api";
import { getCatalogEntity, listSources } from "./api";
import { asApiError, type Load } from "./useLoad";

export const SOURCES_KEY = ["sources"] as const;
const listKey = [...SOURCES_KEY, "list"] as const;
const catalogKey = (type: CatalogEntityType, fqn: string) =>
  [...SOURCES_KEY, "catalog", type, fqn] as const;

function toLoad<T>(q: {
  data?: T;
  error: unknown;
  isPending: boolean;
  isError: boolean;
}): Load<T> {
  if (q.isError) return { status: "error", error: asApiError(q.error) };
  if (q.isPending) return { status: "loading" };
  return { status: "ready", data: q.data as T };
}

const options = {
  retry: false,
  refetchOnWindowFocus: false,
  staleTime: 0,
} as const;

export function useSources() {
  const q = useQuery({ queryKey: listKey, queryFn: listSources, ...options });
  return {
    state: toLoad<SourceSummary[]>(q),
    reload: (_quiet = false) => void q.refetch(),
  };
}

export function useCatalogEntity(
  type: CatalogEntityType,
  fqn: string,
  enabled = true,
) {
  const q = useQuery({
    queryKey: catalogKey(type, fqn),
    queryFn: () => getCatalogEntity(type, fqn),
    enabled,
    ...options,
  });
  return { state: toLoad<CatalogEntity>(q), reload: () => void q.refetch() };
}

/** 数据源相关数据全部失效（运行结束、保存配置、编辑属性后调用） */
export function useInvalidateSources() {
  const client = useQueryClient();
  return useCallback(
    () => client.invalidateQueries({ queryKey: SOURCES_KEY }),
    [client],
  );
}
