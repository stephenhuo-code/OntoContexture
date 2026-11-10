import { createContext, useContext, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import type { BrowseNode, BrowseStep } from "@contexture/ts-api";
import { NavIcon } from "../../layout/NavIcon";
import { useAssetsCriteria } from "./criteria";
import { typeIcon, typeLabel } from "./labels";
import { useBrowse } from "./queries";

const keyOf = (path: BrowseStep[]) =>
  path.map((s) => `${s.level}:${s.value}`).join("/");

const Ctx = createContext<{
  expanded: Set<string>;
  toggle: (k: string) => void;
  pick: (path: BrowseStep[]) => void;
  current: string;
} | null>(null);

function nodeLabel(n: BrowseNode) {
  return n.level === "entityType" ? typeLabel(n.value) : n.label;
}

function Level({ path, depth }: { path: BrowseStep[]; depth: number }) {
  const { criteria } = useAssetsCriteria();
  const q = useBrowse(criteria, path);
  if (q.state.status === "loading")
    return <p className="catalog-note">正在读取…</p>;
  if (q.state.status === "error")
    return (
      <p className="catalog-note error" role="alert">
        浏览树读取失败 · {q.state.error.code}{" "}
        <button type="button" className="link-button" onClick={q.reload}>
          重试
        </button>
      </p>
    );
  if (!q.state.data.nodes.length && depth === 0)
    return <p className="catalog-note">暂无数据资产</p>;
  return (
    <ul className="browse-tree__level">
      {q.state.data.nodes.map((n) => (
        <Row key={`${n.level}:${n.value}`} node={n} path={path} depth={depth} />
      ))}
    </ul>
  );
}

function Row({
  node,
  path,
  depth,
}: {
  node: BrowseNode;
  path: BrowseStep[];
  depth: number;
}) {
  const ctx = useContext(Ctx)!;
  const label = nodeLabel(node);
  const here = [...path, { level: node.level, value: node.value, label }];
  const key = keyOf(here);
  const open = ctx.expanded.has(key);
  return (
    <li>
      <div className="browse-tree__row" style={{ paddingLeft: depth * 14 }}>
        {node.hasChildren ? (
          <button
            type="button"
            className={`browse-tree__toggle${open ? " is-open" : ""}`}
            aria-expanded={open}
            aria-label={`${open ? "收起" : "展开"} ${label}`}
            onClick={() => ctx.toggle(key)}
          >
            <NavIcon name="chevron" />
          </button>
        ) : (
          <span className="browse-tree__toggle" />
        )}
        <button
          type="button"
          className="browse-tree__pick"
          aria-current={ctx.current === key ? "true" : undefined}
          onClick={() => ctx.pick(here)}
        >
          {node.level === "entityType" && (
            <NavIcon name={typeIcon(node.value)} />
          )}
          <span className="browse-tree__label">{label}</span>{" "}
          <span className="browse-tree__count">{node.count}</span>
        </button>
      </div>
      {open && <Level path={here} depth={depth + 1} />}
    </li>
  );
}

/** 浏览树（FR-006，由 005 目录树改造）：计数来自 OM 搜索聚合；展开时才加载；点击只设置位置条件、不跳页。 */
export function BrowseTree({ onPick }: { onPick?: () => void }) {
  const { criteria, dispatch } = useAssetsCriteria();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const value = {
    expanded,
    current: keyOf(criteria.browsePath),
    toggle: (k: string) =>
      setExpanded((s) => {
        const next = new Set(s);
        if (next.has(k)) next.delete(k);
        else next.add(k);
        return next;
      }),
    pick: (path: BrowseStep[]) => {
      dispatch({ type: "browse", path });
      if (pathname.replace(/\/+$/, "") !== "/assets") navigate("/assets");
      onPick?.();
    },
  };
  return (
    <Ctx.Provider value={value}>
      <nav className="browse-tree catalog-nav" aria-label="数据资产浏览树">
        <Level path={[]} depth={0} />
      </nav>
    </Ctx.Provider>
  );
}
