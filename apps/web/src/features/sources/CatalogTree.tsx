import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import type { CatalogEntityType, ServiceType } from "@contexture/ts-api";
import { NavIcon } from "../../layout/NavIcon";
import { ConnectorBadge } from "./SourcesList";
import { CHILD_TYPE, assetChain, assetHref } from "./format";
import { useCatalogEntity, useInvalidateSources, useSources } from "./queries";

type Node = {
  type: CatalogEntityType;
  fqn: string;
  service: string;
  label: string;
  hint?: string;
  expandable: boolean;
  serviceType?: ServiceType;
};

const TYPE_ICON: Record<CatalogEntityType, string> = {
  databaseService: "database",
  database: "database",
  databaseSchema: "schema",
  table: "table",
};
type Child = {
  entityType?: string;
  name?: string;
  fullyQualifiedName?: string;
  displayName?: string | null;
  childCount?: number;
};

const keyOf = (type: string, fqn: string) => `${type}:${fqn}`;

/** 当前地址对应的资产（/sources/:service 或 /sources/:service/assets/:type/:fqn） */
function currentAsset(
  pathname: string,
): { type: CatalogEntityType; fqn: string } | null {
  const m = /^\/sources\/([^/]+)(?:\/assets\/([^/]+)\/([^/]+))?\/?$/.exec(
    pathname,
  );
  if (!m || m[1] === undefined) return null;
  if (!m[2]) return { type: "databaseService", fqn: decodeURIComponent(m[1]) };
  return {
    type: m[2] as CatalogEntityType,
    fqn: decodeURIComponent(m[3] ?? ""),
  };
}

type TreeCtx = {
  expanded: Set<string>;
  toggle: (key: string) => void;
  currentKey: string;
  pick: (n: Node) => void;
};

/** 某个已展开节点的直接子项：订阅共享缓存，数据源相关数据失效时自动重新读取 */
function ChildRows({
  node,
  depth,
  ctx,
}: {
  node: Node;
  depth: number;
  ctx: TreeCtx;
}) {
  const sub = useCatalogEntity(node.type, node.fqn);
  if (sub.state.status === "loading")
    return <p className="catalog-note">正在读取…</p>;
  if (sub.state.status === "error")
    return (
      <p className="catalog-note error" role="alert">
        读取失败 · {sub.state.error.code}
      </p>
    );
  const childType = CHILD_TYPE[node.type];
  const nodes = ((sub.state.data.children ?? []) as Child[]).map((c): Node => ({
    type: (c.entityType as CatalogEntityType) ?? childType,
    fqn: c.fullyQualifiedName ?? "",
    service: node.service,
    label: c.displayName || c.name || "",
    expandable: c.entityType !== "table" && (c.childCount ?? 0) > 0,
  }));
  return nodes.length ? (
    <Rows nodes={nodes} depth={depth} ctx={ctx} />
  ) : (
    <p className="catalog-note">暂无元数据</p>
  );
}

function Rows({
  nodes,
  depth,
  ctx,
}: {
  nodes: Node[];
  depth: number;
  ctx: TreeCtx;
}) {
  return (
    <ul>
      {nodes.map((n) => {
        const key = keyOf(n.type, n.fqn);
        const open = n.expandable && ctx.expanded.has(key);
        const active = ctx.currentKey === key;
        return (
          <li key={key}>
            <div
              className={`catalog-row${active ? " selected" : ""}`}
              style={{ paddingLeft: depth * 12 }}
            >
              {n.expandable ? (
                <button
                  type="button"
                  className="catalog-toggle"
                  aria-label={`${open ? "收起" : "展开"} ${n.label}`}
                  aria-expanded={open}
                  onClick={() => ctx.toggle(key)}
                >
                  <NavIcon
                    name="chevron"
                    className={open ? "open" : undefined}
                  />
                </button>
              ) : (
                <span className="catalog-toggle" />
              )}
              <button
                type="button"
                className="catalog-pick"
                title={n.fqn}
                aria-current={active ? "page" : undefined}
                onClick={() => ctx.pick(n)}
              >
                {n.serviceType ? (
                  <ConnectorBadge type={n.serviceType} />
                ) : (
                  <NavIcon name={TYPE_ICON[n.type]} className="catalog-icon" />
                )}
                <span>{n.label}</span>
                {n.hint && <small>{n.hint}</small>}
              </button>
            </div>
            {open && <ChildRows node={n} depth={depth + 1} ctx={ctx} />}
          </li>
        );
      })}
    </ul>
  );
}

/** 四层目录树（服务 → 数据库 → Schema → 表）：逐层实时读取 BFF 目录实体，不内置任何示例节点。 */
export function CatalogTree({ onPick }: { onPick?: () => void }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const sources = useSources();
  const invalidate = useInvalidateSources();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const current = currentAsset(pathname);
  const currentKey = current ? keyOf(current.type, current.fqn) : "";

  // 进入数据源列表或某个数据源详情时重新读取（后台定时运行结束时 OM 不推送通知）
  const onSourcePage = /^\/sources(\/[^/]+)?\/?$/.test(pathname);
  useEffect(() => {
    if (onSourcePage) void invalidate();
  }, [pathname, onSourcePage, invalidate]);

  // 进入资产页时自动展开其上级节点
  useEffect(() => {
    if (!current || current.type === "databaseService") return;
    const chain = assetChain(current.type, current.fqn).slice(0, -1);
    setExpanded(
      (s) => new Set([...s, ...chain.map((c) => keyOf(c.type, c.fqn))]),
    );
  }, [currentKey]);

  const ctx: TreeCtx = {
    expanded,
    currentKey,
    toggle: (key) =>
      setExpanded((s) => {
        const next = new Set(s);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      }),
    pick: (n) => {
      navigate(assetHref(n.service, n.type, n.fqn));
      onPick?.();
    },
  };

  return (
    <nav className="catalog-nav" aria-label="数据源目录">
      {sources.state.status === "loading" && (
        <p className="catalog-note">正在读取目录…</p>
      )}
      {sources.state.status === "error" && (
        <p className="catalog-note error" role="alert">
          目录读取失败 · {sources.state.error.code}{" "}
          <button
            type="button"
            className="link-button"
            onClick={() => sources.reload()}
          >
            重试
          </button>
        </p>
      )}
      {sources.state.status === "ready" &&
        (sources.state.data.length ? (
          <Rows
            nodes={sources.state.data.map((s) => ({
              type: "databaseService" as const,
              fqn: s.name,
              service: s.name,
              label: s.name,
              hint:
                s.configured && s.tableCount > 0
                  ? String(s.tableCount)
                  : "未采集",
              expandable: s.configured && s.tableCount > 0,
              serviceType: s.serviceType,
            }))}
            depth={0}
            ctx={ctx}
          />
        ) : (
          <p className="catalog-note">还没有数据源</p>
        ))}
    </nav>
  );
}
