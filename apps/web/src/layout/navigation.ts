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
    label: zh.nav.assets,
    path: "/assets",
    module: "asset",
    secondaryItems: [],
    availability: "not_open",
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
  const primary = primaryRoutes.find(
    (r) => r.path === path || r.secondaryItems.some((s) => s.path === path),
  );
  const current =
    primary?.secondaryItems.find((s) => s.path === path) ?? primary;
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
