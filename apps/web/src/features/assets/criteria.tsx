import {
  createContext,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type {
  BrowseStep,
  EntityType,
  FacetDimension,
  SearchCriteria,
} from "@contexture/ts-api";

/**
 * 006 搜索条件（data-model 第 2 节）：只保存在本次会话的内存中，不写入页面地址（D9），
 * 刷新后回到初始浏览状态。浏览器只把这些结构化条件交给 BFF（FR-019）。
 */
export type SortField = "popularity" | "name" | "relevance" | "updatedAt";
export type SortOrder = "asc" | "desc";
export type PageSize = 15 | 25 | 50;
export type BrowseLevel = BrowseStep["level"];
export type FilterValue = { values: string[]; includeNone: boolean };

export interface Criteria {
  keyword: string;
  scope: EntityType | null;
  entityType: EntityType | null;
  browsePath: BrowseStep[];
  filters: Partial<Record<FacetDimension, FilterValue>>;
  sort: { field: SortField; order: SortOrder };
  page: number;
  pageSize: PageSize;
}

export const PAGE_SIZES: readonly PageSize[] = [15, 25, 50];
export const RESULT_WINDOW = 10000;
export const MAX_KEYWORD = 200;

export const initialCriteria: Criteria = {
  keyword: "",
  scope: null,
  entityType: null,
  browsePath: [],
  filters: {},
  sort: { field: "popularity", order: "desc" },
  page: 1,
  pageSize: 15,
};

// 浏览树各层的先后（research R3）：数据库类 root→serviceType→service→database→databaseSchema→entityType；
// 其他大类 root→serviceType→service→entityType；治理类 root→entityType
const NEXT: Record<BrowseLevel, readonly BrowseLevel[]> = {
  root: ["serviceType", "entityType"],
  serviceType: ["service"],
  service: ["database", "entityType"],
  database: ["databaseSchema"],
  databaseSchema: ["entityType"],
  entityType: [],
};

export function validBrowsePath(path: readonly BrowseStep[]): boolean {
  if (path.length === 0) return true;
  if (path.length > 6 || path[0]?.level !== "root") return false;
  return path.every(
    (step, i) => i === 0 || NEXT[path[i - 1]!.level].includes(step.level),
  );
}

export const withinWindow = (page: number, pageSize: number) =>
  page >= 1 && (page - 1) * pageSize + pageSize <= RESULT_WINDOW;

export type CriteriaAction =
  | { type: "keyword"; keyword: string }
  | { type: "scope"; scope: EntityType | null }
  | { type: "entityType"; entityType: EntityType | null }
  | { type: "browse"; path: readonly BrowseStep[] }
  | { type: "removeBrowseLevel"; index: number }
  | {
      type: "filter";
      dimension: FacetDimension;
      values: readonly string[];
      includeNone: boolean;
    }
  | { type: "sort"; field: SortField; order: SortOrder }
  | { type: "page"; page: number }
  | { type: "pageSize"; pageSize: number }
  | { type: "clearAll" };

export function criteriaReducer(
  state: Criteria,
  action: CriteriaAction,
): Criteria {
  switch (action.type) {
    case "keyword":
      return {
        ...state,
        keyword: action.keyword.trim().slice(0, MAX_KEYWORD),
        page: 1,
      };
    case "scope":
      return { ...state, scope: action.scope, page: 1 };
    case "entityType":
      return { ...state, entityType: action.entityType, page: 1 };
    case "browse":
      if (!validBrowsePath(action.path))
        throw new Error("位置条件不合法：第一层必须是大类，且不能跳层");
      return { ...state, browsePath: [...action.path], page: 1 };
    case "removeBrowseLevel":
      return {
        ...state,
        browsePath: state.browsePath.slice(0, action.index),
        page: 1,
      };
    case "filter": {
      const filters = { ...state.filters };
      if (action.values.length || action.includeNone)
        filters[action.dimension] = {
          values: [...action.values],
          includeNone: action.includeNone,
        };
      else delete filters[action.dimension];
      return { ...state, filters, page: 1 };
    }
    case "sort":
      return {
        ...state,
        sort: { field: action.field, order: action.order },
        page: 1,
      };
    case "page":
      if (!withinWindow(action.page, state.pageSize))
        throw new Error("页码超出 10000 条结果窗口");
      return { ...state, page: action.page };
    case "pageSize":
      if (!PAGE_SIZES.includes(action.pageSize as PageSize))
        throw new Error("每页条数只能是 15 / 25 / 50");
      return { ...state, pageSize: action.pageSize as PageSize, page: 1 };
    case "clearAll":
      return {
        ...state,
        keyword: "",
        entityType: null,
        browsePath: [],
        filters: {},
        page: 1,
      };
  }
}

/** 转为契约中的 SearchCriteria（只含非空条件）。 */
export function toRequest(c: Criteria): SearchCriteria {
  return {
    keyword: c.keyword,
    scope: c.scope,
    entityType: c.entityType,
    browsePath: c.browsePath,
    filters: c.filters,
    sort: c.sort,
    page: c.page,
    pageSize: c.pageSize,
  };
}

const Ctx = createContext<{
  criteria: Criteria;
  dispatch: Dispatch<CriteriaAction>;
} | null>(null);

export function AssetsCriteriaProvider({ children }: { children: ReactNode }) {
  const parent = useContext(Ctx);
  if (parent) return <>{children}</>;
  return <Provider>{children}</Provider>;
}

function Provider({ children }: { children: ReactNode }) {
  const [criteria, dispatch] = useReducer(criteriaReducer, initialCriteria);
  const value = useMemo(() => ({ criteria, dispatch }), [criteria]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAssetsCriteria() {
  const v = useContext(Ctx);
  if (!v)
    throw new Error("useAssetsCriteria 须在 AssetsCriteriaProvider 内使用");
  return v;
}
