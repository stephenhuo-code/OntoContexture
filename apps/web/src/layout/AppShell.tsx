import { Outlet, useLocation } from "react-router";
import { PrimaryNav } from "./PrimaryNav";
import { SecondaryNav } from "./SecondaryNav";
import { PageHeader } from "./PageHeader";
import { routePresentation } from "./navigation";
export function AppShell({
  secondaryOpen,
  toggleSecondary,
}: {
  secondaryOpen: boolean;
  toggleSecondary: () => void;
}) {
  const { pathname } = useLocation();
  const route = routePresentation(pathname);
  const hasSecondary = !!route.primary?.secondaryItems.length;
  return (
    <div className="app-shell">
      <PrimaryNav current={route.primary} />
      {hasSecondary && secondaryOpen && route.primary && (
        <SecondaryNav route={route.primary} path={route.path} />
      )}
      <div className="workspace">
        <PageHeader
          title={route.title}
          hasSecondary={hasSecondary}
          secondaryOpen={secondaryOpen}
          toggle={toggleSecondary}
        />
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
