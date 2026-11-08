import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import type { CatalogEntityType, ServiceType } from "@contexture/ts-api";
import { NavIcon } from "../../layout/NavIcon";
import { ConnectorBadge } from "./SourcesList";
import { getCatalogEntity, listSources } from "./api";
import { CHILD_TYPE, assetChain, assetHref, splitFqn } from "./format";
import { asApiError, useLoad, type Load } from "./useLoad";

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

/** 四层目录树（服务 → 数据库 → Schema → 表）：逐层实时读取 BFF 目录实体，不内置任何示例节点。 */
export function CatalogTree({ onPick }: { onPick?: () => void }) {
  const { pathname, state } = useLocation();
  const navigate = useNavigate();
  const saved = (state as { saved?: number } | null)?.saved;
  const sources = useLoad(listSources, [saved]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [children, setChildren] = useState<Record<string, Load<Node[]>>>({});
  const current = currentAsset(pathname);

  const load = (n: Node) => {
    const key = keyOf(n.type, n.fqn);
    setChildren((c) => ({ ...c, [key]: { status: "loading" } }));
    getCatalogEntity(n.type, n.fqn).then(
      (e) => {
        const childType = CHILD_TYPE[n.type];
        const data = ((e.children ?? []) as Child[]).map((c): Node => ({
          type: (c.entityType as CatalogEntityType) ?? childType,
          fqn: c.fullyQualifiedName ?? "",
          service: n.service,
          label: c.displayName || c.name || "",
          expandable: c.entityType !== "table" && (c.childCount ?? 0) > 0,
        }));
        setChildren((c) => ({ ...c, [key]: { status: "ready", data } }));
      },
      (err: unknown) =>
        setChildren((c) => ({
          ...c,
          [key]: { status: "error", error: asApiError(err) },
        })),
    );
  };

  // 进入资产页时自动展开其上级节点
  const chainKey = current ? keyOf(current.type, current.fqn) : "";
  useEffect(() => {
    if (!current || current.type === "databaseService") return;
    const service = splitFqn(current.fqn)[0] ?? "";
    const chain = assetChain(current.type, current.fqn).slice(0, -1);
    setExpanded(
      (s) => new Set([...s, ...chain.map((c) => keyOf(c.type, c.fqn))]),
    );
    for (const c of chain) {
      const key = keyOf(c.type, c.fqn);
      if (!children[key])
        load({
          type: c.type,
          fqn: c.fqn,
          service,
          label: c.label,
          expandable: true,
        });
    }
  }, [chainKey]);

  const toggle = (n: Node) => {
    const key = keyOf(n.type, n.fqn);
    const next = new Set(expanded);
    if (next.has(key)) next.delete(key);
    else {
      next.add(key);
      if (!children[key] || children[key]?.status === "error") load(n);
    }
    setExpanded(next);
  };

  const rows = (nodes: Node[], depth: number) => (
    <ul>
      {nodes.map((n) => {
        const key = keyOf(n.type, n.fqn);
        const open = expanded.has(key);
        const active = current && keyOf(current.type, current.fqn) === key;
        const sub = children[key];
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
                  onClick={() => toggle(n)}
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
                onClick={() => {
                  navigate(assetHref(n.service, n.type, n.fqn));
                  onPick?.();
                }}
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
            {open && sub?.status === "loading" && (
              <p className="catalog-note">正在读取…</p>
            )}
            {open && sub?.status === "error" && (
              <p className="catalog-note error" role="alert">
                读取失败 · {sub.error.code}
              </p>
            )}
            {open &&
              sub?.status === "ready" &&
              (sub.data.length ? (
                rows(sub.data, depth + 1)
              ) : (
                <p className="catalog-note">暂无元数据</p>
              ))}
          </li>
        );
      })}
    </ul>
  );

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
          rows(
            sources.state.data.map((s) => ({
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
            })),
            0,
          )
        ) : (
          <p className="catalog-note">还没有数据源</p>
        ))}
    </nav>
  );
}
