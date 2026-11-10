import { useState, type ReactNode, type PointerEvent } from "react";
import { Link } from "react-router";
import { zh } from "../i18n/zh-CN";
import { NavIcon } from "./NavIcon";
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

const MODULE_ICON: Record<RouteEntry["module"], string> = {
  home: "home",
  asset: "module-asset",
  agent: "agents",
};
const ITEM_ICON: Record<string, string> = {
  overview: "overview",
  approvals: "approval",
};

// 二级栏宽度：可拖动或用方向键调整（与 OpenMetadata 左栏一致）；仅保存在本人浏览器
const WIDTH_KEY = "ctx.secondaryWidth";
const MIN_WIDTH = 200;
const MAX_WIDTH = 480;
const DEFAULT_WIDTH = 236;
const clamp = (w: number) =>
  Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(w)));

function storedWidth(): number {
  try {
    const v = Number(localStorage.getItem(WIDTH_KEY));
    return v ? clamp(v) : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
}

function useRailWidth() {
  const [width, setWidth] = useState(storedWidth);
  const set = (w: number) => {
    const next = clamp(w);
    setWidth(next);
    try {
      localStorage.setItem(WIDTH_KEY, String(next));
    } catch {
      /* 浏览器禁用存储时只在本次页面内生效 */
    }
  };
  return [width, set] as const;
}

export function SecondaryNav({
  route,
  path,
  children,
}: {
  route: RouteEntry;
  path: string;
  /** 二级栏下方的附加内容（资产工作空间：目录树） */
  children?: ReactNode;
}) {
  const text = moduleText[route.module];
  const current = path;
  const [width, setWidth] = useRailWidth();
  const drag = (e: PointerEvent<HTMLDivElement>) => {
    e.preventDefault(); // 拖动时不选中页面文字
    const startX = e.clientX;
    const startW = width;
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const move = (ev: globalThis.PointerEvent) =>
      setWidth(startW + ev.clientX - startX);
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      document.body.classList.remove("resizing");
    };
    document.body.classList.add("resizing");
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
  };
  return (
    <aside
      className="secondary-rail"
      id="secondary-navigation"
      style={{ width, flexBasis: width }}
    >
      <div className="module-label">
        <NavIcon name={MODULE_ICON[route.module]} />
        {text.title ?? route.label}
      </div>
      {route.secondaryItems.length > 0 && (
        <nav aria-label={text.aria}>
          {route.secondaryItems.map((item) => (
            <Link
              key={item.id}
              to={item.path}
              aria-current={current === item.path ? "page" : undefined}
            >
              <NavIcon name={ITEM_ICON[item.id] ?? "overview"} />
              {item.label}
            </Link>
          ))}
        </nav>
      )}
      {children}
      <div
        role="separator"
        aria-label="调整二级栏宽度"
        aria-orientation="vertical"
        aria-valuemin={MIN_WIDTH}
        aria-valuemax={MAX_WIDTH}
        aria-valuenow={width}
        tabIndex={0}
        className="rail-resizer"
        onPointerDown={drag}
        onDoubleClick={() => setWidth(DEFAULT_WIDTH)}
        onKeyDown={(e) => {
          const step = { ArrowLeft: -16, ArrowRight: 16 }[e.key];
          if (step) setWidth(width + step);
          else if (e.key === "Home") setWidth(MIN_WIDTH);
          else if (e.key === "End") setWidth(MAX_WIDTH);
          else return;
          e.preventDefault();
        }}
      />
    </aside>
  );
}
