// 织境 bff 的类型化客户端（同源访问，浏览器只携带会话 Cookie）
import createClient from "openapi-fetch";

import type { components, paths } from "./bff";

export type ObjectListView = components["schemas"]["ObjectListView"];
export type ObjectTypeRef = components["schemas"]["ObjectTypeRef"];
export type ObjectInstance = components["schemas"]["ObjectInstance"];
export type Me = components["schemas"]["Me"];

// 005 源系统元数据采集
export type ServiceType = components["schemas"]["ServiceType"];
export type PipelineState = components["schemas"]["PipelineState"];
export type ConnectionInput = components["schemas"]["ConnectionInput"];
export type FilterPattern = components["schemas"]["FilterPattern"];
export type Scope = components["schemas"]["Scope"];
export type Schedule = components["schemas"]["Schedule"];
export type SourceUpsert = components["schemas"]["SourceUpsert"];
export type PipelineSummary = components["schemas"]["PipelineSummary"];
export type PipelineRun = components["schemas"]["PipelineRun"];
export type SourceSummary = components["schemas"]["SourceSummary"];
export type SourceDetail = components["schemas"]["SourceDetail"];
export type TestConnectionResult =
  components["schemas"]["TestConnectionResult"];
export type GovernanceValues = components["schemas"]["GovernanceValues"];
export type GovernancePatch = components["schemas"]["GovernancePatch"];
export type CatalogEntity = components["schemas"]["CatalogEntity"];
export type EntityRef = components["schemas"]["Ref"];
export type GovernanceOptions = components["schemas"]["GovernanceOptions"];
export type PipelineKind = "metadata" | "lineage";
export type CatalogEntityType = CatalogEntity["entityType"];

// 006 资产搜索与摘要
export type EntityType = components["schemas"]["EntityType"];
export type FacetDimension = components["schemas"]["FacetDimension"];
export type BrowseStep = components["schemas"]["BrowseStep"];
export type SearchCriteria = components["schemas"]["SearchCriteria"];
export type AssetRef = components["schemas"]["AssetRef"];
export type TextSegment = components["schemas"]["TextSegment"];
export type GovernanceSummary = components["schemas"]["GovernanceSummary"];
export type SearchHit = components["schemas"]["SearchHit"];
export type SearchPage = components["schemas"]["SearchPage"];
export type TypeCounts = components["schemas"]["TypeCounts"];
export type FacetOption = components["schemas"]["FacetOption"];
export type BrowseNode = components["schemas"]["BrowseNode"];
export type Suggestion = components["schemas"]["Suggestion"];
export type SummaryColumn = components["schemas"]["SummaryColumn"];
export type AssetSummary = components["schemas"]["AssetSummary"];
export type GlossaryTermDetail = components["schemas"]["GlossaryTermDetail"];
export type TagDetail = components["schemas"]["TagDetail"];

/** 统一错误格式（contracts/schemas/error.json） */
export interface ApiError {
  code: string;
  message: string;
  trace_id: string;
  details?: Record<string, unknown>;
}

export function createBffClient(baseUrl = "") {
  return createClient<paths>({
    baseUrl,
    credentials: "same-origin",
    // 每次请求时取全局 fetch（便于测试替换，也兼容运行时注入的 fetch）
    fetch: (request) => globalThis.fetch(request),
  });
}

export type BffClient = ReturnType<typeof createBffClient>;
