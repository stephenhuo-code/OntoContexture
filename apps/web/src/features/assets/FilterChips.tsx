import type { FacetDimension } from "@contexture/ts-api";
import { useAssetsCriteria } from "./criteria";
import { DIMENSION_LABEL } from "./labels";

/** 条件条（FR-009）：位置条件逐层显示（删除某层连同下层），筛选值可单独删除，「清除全部」。 */
export function FilterChips() {
  const { criteria, dispatch } = useAssetsCriteria();
  const filters = Object.entries(criteria.filters) as [
    FacetDimension,
    NonNullable<(typeof criteria.filters)[FacetDimension]>,
  ][];
  const any =
    !!criteria.keyword || criteria.browsePath.length > 0 || filters.length > 0;
  return (
    <section className="filter-chips" aria-label="条件条">
      {!any && (
        <p className="filter-chips__hint">
          提示：点击左侧浏览树节点可按层级筛选位置（不跳转页面），也可使用上方搜索框或快速筛选组合过滤资产。
        </p>
      )}
      {criteria.browsePath.map((s, i) => {
        const label = s.label || s.value;
        return (
          <span
            key={`${s.level}:${s.value}`}
            className="filter-chip filter-chip--place"
          >
            {i === 0 ? "在 " : ""}
            {label}
            <button
              type="button"
              aria-label={`移除位置 ${label}`}
              onClick={() => dispatch({ type: "removeBrowseLevel", index: i })}
            >
              ×
            </button>
          </span>
        );
      })}
      {filters.flatMap(([dim, f]) => {
        const name = DIMENSION_LABEL[dim];
        const chips = f.values.map((v) => {
          const label = f.labels?.[v] ?? v;
          return (
            <span key={`${dim}:${v}`} className="filter-chip">
              {name}：{label}
              <button
                type="button"
                aria-label={`移除 ${name}：${label}`}
                onClick={() =>
                  dispatch({
                    type: "filter",
                    dimension: dim,
                    values: f.values.filter((x) => x !== v),
                    includeNone: f.includeNone,
                  })
                }
              >
                ×
              </button>
            </span>
          );
        });
        if (f.includeNone)
          chips.push(
            <span key={`${dim}:none`} className="filter-chip">
              {name}：无
              <button
                type="button"
                aria-label={`移除 ${name}：无`}
                onClick={() =>
                  dispatch({
                    type: "filter",
                    dimension: dim,
                    values: f.values,
                    includeNone: false,
                  })
                }
              >
                ×
              </button>
            </span>,
          );
        return chips;
      })}
      {any && (
        <button
          type="button"
          className="link-button"
          onClick={() => dispatch({ type: "clearAll" })}
        >
          清除全部
        </button>
      )}
    </section>
  );
}
