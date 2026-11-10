import { useAssetsCriteria, type SortField } from "./criteria";
import { SORT_LABEL } from "./labels";

/** 排序（FR-010）：热度（默认）、名称、相关性、最近更新；默认降序；改变排序回到第 1 页。 */
export function SortControl() {
  const { criteria, dispatch } = useAssetsCriteria();
  const { field, order } = criteria.sort;
  return (
    <div className="asset-sort">
      <select
        aria-label="排序"
        value={field}
        onChange={(e) =>
          dispatch({ type: "sort", field: e.target.value as SortField, order })
        }
      >
        {(Object.keys(SORT_LABEL) as SortField[]).map((k) => (
          <option key={k} value={k}>
            {SORT_LABEL[k]}
          </option>
        ))}
      </select>
      <button
        type="button"
        aria-label={order === "desc" ? "降序" : "升序"}
        title="切换升序 / 降序"
        onClick={() =>
          dispatch({
            type: "sort",
            field,
            order: order === "desc" ? "asc" : "desc",
          })
        }
      >
        {order === "desc" ? "↓" : "↑"}
      </button>
    </div>
  );
}
