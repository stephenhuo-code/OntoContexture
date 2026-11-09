import type { EntityType } from "@contexture/ts-api";
import { useAssetsCriteria } from "./criteria";
import { effectiveRequest } from "./explore";
import { typeLabel } from "./labels";
import { useTypeCounts } from "./queries";

/** 有关键词时的左栏类型列表（FR-007）：只列命中计数大于 0 的类型；切换类型只刷新列表。 */
export function TypeList() {
  const { criteria, dispatch } = useAssetsCriteria();
  const counts = useTypeCounts(criteria);
  const active = effectiveRequest(criteria, counts.state).entityType;
  return (
    <nav className="type-list" aria-label="资产类型">
      {counts.state.status === "loading" && (
        <p className="catalog-note">正在统计类型…</p>
      )}
      {counts.state.status === "error" && (
        <p className="catalog-note error" role="alert">
          类型计数读取失败 · {counts.state.error.code}{" "}
          <button type="button" className="link-button" onClick={counts.reload}>
            重试
          </button>
        </p>
      )}
      {counts.state.status === "ready" &&
        counts.state.data.counts.map((c) => (
          <button
            key={c.entityType}
            type="button"
            aria-pressed={active === c.entityType}
            onClick={() => {
              if (criteria.scope && criteria.scope !== c.entityType)
                dispatch({ type: "scope", scope: null });
              dispatch({
                type: "entityType",
                entityType: c.entityType as EntityType,
              });
            }}
          >
            {typeLabel(c.entityType)}
            <span className="type-list__count">{c.count}</span>
          </button>
        ))}
    </nav>
  );
}
