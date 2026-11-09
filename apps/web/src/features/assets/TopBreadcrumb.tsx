import { Link, useLocation } from "react-router";
import { fqnLabel, splitFqn } from "../sources/format";
import { useAssetsCriteria } from "./criteria";

/** 顶栏面包屑（spec 界面基线第 3 条；research R14）：第一段「数据资产」可返回探索视图并保留条件。 */
export function TopBreadcrumb() {
  const { pathname } = useLocation();
  const { criteria } = useAssetsCriteria();
  const trail: string[] = [];
  const sub = pathname.replace(/^\/assets\/?/, "");
  if (sub.startsWith("sources")) trail.push("数据源管理");
  else if (sub) {
    const [, fqn = ""] = sub.split("/");
    const parts = splitFqn(decodeURIComponent(fqn)).map(fqnLabel);
    if (parts.length > 1) trail.push(parts[0] ?? "");
    trail.push(parts.at(-1) ?? "");
  } else
    trail.push(...criteria.browsePath.slice(1).map((s) => s.label ?? s.value));
  return (
    <div className="asset-breadcrumb">
      <h1>
        <Link to="/assets">数据资产</Link>
      </h1>
      {trail.map((t, i) => (
        <span key={i}>
          <span aria-hidden="true">/</span>
          {i === trail.length - 1 ? <strong>{t}</strong> : t}
        </span>
      ))}
    </div>
  );
}
