import { Outlet, useLocation } from "react-router";
import { PrimaryNav } from "./PrimaryNav";
import { SecondaryNav } from "./SecondaryNav";
import { PageHeader } from "./PageHeader";
import { routePresentation } from "./navigation";
import { AssetsRail } from "../features/assets/AssetsRail";
import { AssetsCriteriaProvider } from "../features/assets/criteria";
import { SearchBar } from "../features/assets/SearchBar";
import { TopBreadcrumb } from "../features/assets/TopBreadcrumb";
export function AppShell({
  secondaryOpen,
  toggleSecondary,
}: {
  secondaryOpen: boolean;
  toggleSecondary: () => void;
}) {
  const { pathname } = useLocation();
  const route = routePresentation(pathname);
  // 006：资产工作空间没有二级链接，二级栏只承载目录树（US2 起为浏览树 / 类型列表）
  const hasSecondary =
    !!route.primary?.secondaryItems.length || route.primary?.module === "asset";
  const assets = route.primary?.module === "asset";
  return (
    <AssetsCriteriaProvider>
      <div className="app-shell">
        <PrimaryNav current={route.primary} />
        {hasSecondary && secondaryOpen && route.primary && (
          <SecondaryNav route={route.primary} path={route.path}>
            {assets && <AssetsRail />}
          </SecondaryNav>
        )}
        <div className="workspace">
          <PageHeader
            title={route.title}
            hasSecondary={hasSecondary}
            secondaryOpen={secondaryOpen}
            toggle={toggleSecondary}
            heading={assets ? <TopBreadcrumb /> : undefined}
            center={assets ? <SearchBar /> : undefined}
          />
          <main className="page-content">
            <Outlet />
          </main>
        </div>
      </div>
    </AssetsCriteriaProvider>
  );
}
