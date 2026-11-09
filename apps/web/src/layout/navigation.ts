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
    path: "/assets",
    module: "asset",
    // 006 D2：二级栏不再放「资产搜索」「数据源」链接，只承载浏览树或类型列表
    secondaryItems: [],
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
  // 006：/assets 下的探索、数据源管理与资产详情同属「数据资产」页面
  const base = path.startsWith("/assets/") ? "/assets" : path;
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
      (base === "/assets" ? zh.nav.assetModule : current?.label) ??
      (/^\/objects\/[^/]+$/.test(path)
        ? zh.nav.legacy
        : path === "/__dev/ui" && examplesEnabled
          ? zh.examples.title
          : zh.notFound),
  };
}
