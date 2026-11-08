import type { ReactNode } from "react";
import { Link } from "react-router";
import { zh } from "../i18n/zh-CN";
import type { RouteEntry } from "./navigation";

// 各工作空间的二级栏标题与导航名称；资产工作空间按 005 原型
const moduleText: Record<
  RouteEntry["module"],
  { title?: string; aria: string }
> = {
  home: { aria: zh.nav.secondary },
  asset: { title: zh.nav.assetModule, aria: zh.nav.assetSecondary },
  agent: { aria: zh.nav.secondary },
};

export function SecondaryNav({
  route,
  path,
  children,
}: {
  route: RouteEntry;
  path: string;
  /** 二级栏下方的附加内容（005：数据源目录树） */
  children?: ReactNode;
}) {
  const text = moduleText[route.module];
  const current = path.startsWith("/sources/") ? "/sources" : path;
  return (
    <aside className="secondary-rail" id="secondary-navigation">
      <div className="module-label">{text.title ?? route.label}</div>
      <nav aria-label={text.aria}>
        {route.secondaryItems.map((item) => (
          <Link
            key={item.id}
            to={item.path}
            aria-current={current === item.path ? "page" : undefined}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      {children}
    </aside>
  );
}
