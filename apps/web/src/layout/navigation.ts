import { zh } from "../i18n/zh-CN";
export interface RouteEntry {
  id: string;
  label: string;
  path: string;
  module: "home" | "asset" | "agent";
  secondaryItems: readonly RouteEntry[];
  availability: "shell" | "not_open";
  isAction: boolean;
}
const homeItems: readonly RouteEntry[] = [
  {
    id: "overview",
    label: zh.nav.overview,
    path: "/home",
    module: "home",
    secondaryItems: [],
    availability: "shell",
    isAction: false,
  },
  {
    id: "approvals",
    label: zh.nav.approvals,
    path: "/approvals",
    module: "home",
    secondaryItems: [],
    availability: "not_open",
    isAction: false,
  },
];
// 005：资产工作空间的二级入口；资产搜索归 006（未开放）
const assetItems: readonly RouteEntry[] = [
  {
    id: "asset-search",
    label: zh.nav.assets,
    path: "/assets",
    module: "asset",
    secondaryItems: [],
    availability: "not_open",
    isAction: false,
  },
  {
    id: "sources",
    label: zh.nav.sources,
    path: "/sources",
    module: "asset",
    secondaryItems: [],
    availability: "shell",
    isAction: false,
  },
];
export const primaryRoutes: readonly RouteEntry[] = [
  {
    id: "new",
    label: zh.nav.newChat,
    path: "/agents/new",
    module: "agent",
    secondaryItems: [],
    availability: "not_open",
    isAction: true,
  },
  {
    id: "home",
    label: zh.nav.home,
    path: "/home",
    module: "home",
    secondaryItems: homeItems,
    availability: "shell",
    isAction: false,
  },
  {
    id: "assets",
    label: zh.nav.assetWorkspace,
    path: "/sources",
    module: "asset",
    secondaryItems: assetItems,
    availability: "shell",
    isAction: false,
  },
  {
    id: "agents",
    label: zh.nav.agents,
    path: "/agents",
    module: "agent",
    secondaryItems: [],
    availability: "not_open",
    isAction: false,
  },
];
export const uiExamplesEnabled =
  import.meta.env.DEV || import.meta.env.MODE === "test";
export function routePresentation(
  path: string,
  examplesEnabled = uiExamplesEnabled,
) {
  path = path.replace(/\/+$/, "") || "/";
  // 005：/sources/<服务>… 为数据源详情与目录资产，归属“数据源”入口
  const base = path.startsWith("/sources/") ? "/sources" : path;
  const primary = primaryRoutes.find(
    (r) => r.path === base || r.secondaryItems.some((s) => s.path === base),
  );
  const current =
    primary?.secondaryItems.find((s) => s.path === base) ?? primary;
  return {
    path,
    primary,
    current,
    title:
      current?.label ??
      (/^\/objects\/[^/]+$/.test(path)
        ? zh.nav.legacy
        : path === "/__dev/ui" && examplesEnabled
          ? zh.examples.title
          : zh.notFound),
  };
}
