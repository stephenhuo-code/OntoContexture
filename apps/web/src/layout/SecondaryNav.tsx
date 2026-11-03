import { Link } from "react-router";
import { zh } from "../i18n/zh-CN";
import type { RouteEntry } from "./navigation";
export function SecondaryNav({
  route,
  path,
}: {
  route: RouteEntry;
  path: string;
}) {
  return (
    <aside className="secondary-rail" id="secondary-navigation">
      <div className="module-label">{route.label}</div>
      <nav aria-label={zh.nav.secondary}>
        {route.secondaryItems.map((item) => (
          <Link
            key={item.id}
            to={item.path}
            aria-current={path === item.path ? "page" : undefined}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
