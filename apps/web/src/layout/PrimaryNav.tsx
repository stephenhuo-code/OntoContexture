import { Link } from "react-router";
import { Tooltip } from "@contexture/ui";
import { zh } from "../i18n/zh-CN";
import { NavIcon } from "./NavIcon";
import { primaryRoutes, type RouteEntry } from "./navigation";
export function PrimaryNav({ current }: { current: RouteEntry | undefined }) {
  return (
    <div className="primary-rail">
      <Link className="brand" to="/home" aria-label={zh.brand}>
        <span aria-hidden="true">织</span>
      </Link>
      <span className="rail-divider" aria-hidden="true" />
      <nav aria-label={zh.nav.primary}>
        {primaryRoutes.map((route) => (
          <Tooltip key={route.id} content={route.label}>
            <Link
              to={route.path}
              aria-label={route.label}
              aria-current={route.id === current?.id ? "page" : undefined}
              className={`primary-link${route.isAction ? " primary-action" : ""}`}
            >
              <NavIcon name={route.id} />
            </Link>
          </Tooltip>
        ))}
      </nav>
      <span className="rail-caption" aria-hidden="true">
        {zh.brand}
      </span>
    </div>
  );
}
