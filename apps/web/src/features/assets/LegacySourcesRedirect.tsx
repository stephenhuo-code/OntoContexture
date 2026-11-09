import { Navigate, useLocation } from "react-router";
import { SOURCES_BASE, assetHref } from "../sources/format";
import type { CatalogEntityType } from "@contexture/ts-api";

/** 006 D1：旧的 /sources/* 地址转到 /assets 下对应的新地址（保留查询参数）。 */
export function LegacySourcesRedirect() {
  const { pathname, search } = useLocation();
  const parts = pathname.replace(/\/+$/, "").split("/").slice(2); // 去掉 "" 与 "sources"
  const [service, assets, type, fqn] = parts;
  let to = SOURCES_BASE;
  if (service && assets === "assets" && type && fqn)
    to = assetHref(
      decodeURIComponent(service),
      type as CatalogEntityType,
      decodeURIComponent(fqn),
    );
  else if (service) to = `${SOURCES_BASE}/${service}`;
  return <Navigate to={`${to}${search}`} replace />;
}
