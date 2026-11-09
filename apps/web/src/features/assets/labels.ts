import type { EntityType, FacetDimension } from "@contexture/ts-api";

/**
 * 资产类型的中文名：取 OM 中文界面（openmetadata-ui locale/languages/zh-cn.json），
 * 库 / Schema / 表、业务术语、分类标签沿用 005 与 spec 的叫法。
 */
export const TYPE_LABEL: Record<EntityType, string> = {
  table: "数据表",
  tableColumn: "列",
  storedProcedure: "存储过程",
  databaseSchema: "Schema",
  database: "数据库",
  chart: "图表",
  dashboard: "仪表板",
  dashboardDataModel: "仪表板数据模型",
  pipeline: "工作流",
  topic: "消息主题",
  container: "存储容器",
  directory: "目录",
  file: "文件",
  spreadsheet: "电子表格",
  worksheet: "工作表",
  searchIndex: "搜索索引",
  mlmodel: "机器学习模型",
  dataProduct: "数据产品",
  metric: "指标",
  glossaryTerm: "业务术语",
  tag: "分类标签",
  apiCollection: "API集合",
  apiEndpoint: "API端点",
  page: "页面",
};

export const typeLabel = (t: string) => TYPE_LABEL[t as EntityType] ?? t;

/** 快速筛选维度的文案（spec FR-008） */
export const DIMENSION_LABEL: Record<FacetDimension, string> = {
  entityType: "资产类型",
  domain: "业务域",
  dataProduct: "数据产品",
  owner: "负责人",
  tag: "分类标签",
  tier: "分级（Tier）",
  service: "服务",
  serviceType: "服务类型",
  certification: "认证",
  database: "库",
  databaseSchema: "Schema",
  column: "列",
  tableType: "表类型",
  columnDescriptionStatus: "列描述",
};

/** 排序（spec FR-010 / 页面结构方案） */
export const SORT_LABEL = {
  popularity: "热度",
  name: "名称",
  relevance: "相关性",
  updatedAt: "最近更新",
} as const;

export const ORIGIN_LABEL = {
  devTest: "开发态测试元数据",
  collected: "真实采集来源",
} as const;

const ICON: Partial<Record<string, string>> = {
  table: "table",
  tableColumn: "table",
  database: "database",
  databaseSchema: "schema",
  storedProcedure: "database",
};
export const typeIcon = (t: string) => ICON[t] ?? "overview";
