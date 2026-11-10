import { useEffect, useRef, useState } from "react";
import type { FacetDimension, SearchCriteria } from "@contexture/ts-api";
import { useAssetsCriteria } from "./criteria";
import { DIMENSION_LABEL, typeLabel } from "./labels";
import { useFacet } from "./queries";

// 维度清单与 OM 一致（$UI/constants/AdvancedSearch.constants.ts:20-139；spec FR-008）
const COMMON: FacetDimension[] = [
  "entityType",
  "domain",
  "dataProduct",
  "owner",
  "tag",
  "tier",
  "service",
  "serviceType",
  "certification",
];
const TABLE_ONLY: FacetDimension[] = [
  "database",
  "databaseSchema",
  "column",
  "tableType",
  "columnDescriptionStatus",
];
const NONE: ReadonlySet<FacetDimension> = new Set([
  "owner",
  "domain",
  "tier",
  "tag",
  "certification",
]);

function Menu({
  dimension,
  request,
  onClose,
}: {
  dimension: FacetDimension;
  request: SearchCriteria;
  onClose: () => void;
}) {
  const { criteria, dispatch } = useAssetsCriteria();
  const [query, setQuery] = useState("");
  const facet = useFacet(request, dimension, query.trim(), true);
  const current = criteria.filters[dimension] ?? {
    values: [],
    includeNone: false,
  };
  const label = DIMENSION_LABEL[dimension];
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.parentElement?.contains(e.target as Node))
        onClose();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  const set = (
    values: string[],
    includeNone: boolean,
    labels?: Record<string, string>,
  ) => dispatch({ type: "filter", dimension, values, includeNone, labels });
  const optionLabel = (v: string, l: string) =>
    dimension === "entityType" ? typeLabel(v) : l;
  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={`${label}选项`}
      className="quick-filter__menu"
    >
      <input
        type="search"
        aria-label="搜索选项"
        placeholder="搜索选项"
        value={query}
        maxLength={100}
        onChange={(e) => setQuery(e.target.value)}
      />
      {NONE.has(dimension) && (
        <label className="quick-filter__option">
          <input
            type="checkbox"
            checked={current.includeNone}
            onChange={(e) => set(current.values, e.target.checked)}
          />
          无
        </label>
      )}
      {facet.state.status === "loading" && (
        <p className="catalog-note">正在读取…</p>
      )}
      {facet.state.status === "error" && (
        <p className="catalog-note error" role="alert">
          选项读取失败 · {facet.state.error.code}
        </p>
      )}
      {facet.state.status === "ready" &&
        facet.state.data.options.map((o) => {
          const text = optionLabel(o.value, o.label ?? o.value);
          return (
            <label key={o.value} className="quick-filter__option">
              <input
                type="checkbox"
                aria-label={`${text} ${o.count}`}
                checked={current.values.includes(o.value)}
                onChange={(e) =>
                  set(
                    e.target.checked
                      ? [...current.values, o.value]
                      : current.values.filter((v) => v !== o.value),
                    current.includeNone,
                    { [o.value]: text },
                  )
                }
              />
              <span>{text}</span>
              <span className="quick-filter__count">{o.count}</span>
            </label>
          );
        })}
      {facet.state.status === "ready" && !facet.state.data.options.length && (
        <p className="catalog-note">没有可选项</p>
      )}
    </div>
  );
}

/** 快速筛选（FR-008）：同一维度多选为「或」，跨维度为「且」；计数排除本维度自身的已选条件。 */
export function QuickFilters({
  request,
  tableType,
}: {
  request: SearchCriteria;
  tableType: boolean;
}) {
  const { criteria } = useAssetsCriteria();
  const [open, setOpen] = useState<FacetDimension | null>(null);
  const dims = tableType ? [...COMMON, ...TABLE_ONLY] : COMMON;
  return (
    <div role="group" aria-label="快速筛选" className="quick-filters">
      {dims.map((d) => {
        const active = criteria.filters[d];
        const n = (active?.values.length ?? 0) + (active?.includeNone ? 1 : 0);
        return (
          <div key={d} className="quick-filter">
            <button
              type="button"
              className={`quick-filter__button${n ? " is-active" : ""}`}
              aria-expanded={open === d}
              aria-label={DIMENSION_LABEL[d]}
              onClick={() => setOpen(open === d ? null : d)}
            >
              {DIMENSION_LABEL[d]}
              {n > 0 && <span className="quick-filter__badge">{n}</span>}
            </button>
            {open === d && (
              <Menu
                dimension={d}
                request={request}
                onClose={() => setOpen(null)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
