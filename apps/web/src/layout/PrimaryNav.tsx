import { Link } from "react-router";
import { Tooltip } from "@contexture/ui";
import { zh } from "../i18n/zh-CN";
import { primaryRoutes, type RouteEntry } from "./navigation";
const paths: Record<string, string> = {
  new: "M12 5v14M5 12h14",
  home: "m3 10 9-7 9 7v11h-7v-7h-4v7H3Z",
  assets: "M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16m6-2 6 6",
  agents: "M5 7h14v13H5Zm7-5v5M8 12h1m6 0h1M9 16h6",
};
export function PrimaryNav({ current }: { current: RouteEntry | undefined }) {
  return (
    <div className="primary-rail">
      <Link className="brand" to="/home" aria-label={zh.brand}>
        <span aria-hidden="true">织</span>
      </Link>
      <nav aria-label={zh.nav.primary}>
        {primaryRoutes.map((route) => (
          <Tooltip key={route.id} content={route.label}>
            <Link
              to={route.path}
              aria-label={route.label}
              aria-current={route.id === current?.id ? "page" : undefined}
              className={`primary-link${route.isAction ? " primary-action" : ""}`}
            >
              <svg
                viewBox="0 0 24 24"
                aria-hidden="true"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d={paths[route.id]} />
              </svg>
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
