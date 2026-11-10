import type { SearchCriteria, TypeCounts } from "@contexture/ts-api";
import { toRequest, type Criteria } from "./criteria";
import type { Load } from "../sources/useLoad";

/**
 * 实际查询的条件：有关键词且未指定类型时，等按类型计数返回后取默认类型（FR-007：
 * 首条命中结果的类型，否则计数最多的类型）；没有任何命中时不再查询列表（结果为空）。
 */
export function effectiveRequest(
  criteria: Criteria,
  counts: Load<TypeCounts>,
): { body: SearchCriteria | null; entityType: string | null; empty: boolean } {
  const request = toRequest(criteria);
  if (!criteria.keyword || criteria.entityType || criteria.scope)
    return {
      body: request,
      entityType: criteria.entityType ?? criteria.scope,
      empty: false,
    };
  if (counts.status !== "ready")
    return { body: null, entityType: null, empty: false };
  const type = counts.data.defaultType ?? null;
  if (!type) return { body: null, entityType: null, empty: true };
  return {
    body: { ...request, entityType: type },
    entityType: type,
    empty: false,
  };
}
