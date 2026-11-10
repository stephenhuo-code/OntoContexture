import { PAGE_SIZES, RESULT_WINDOW, useAssetsCriteria } from "./criteria";

/** 分页（FR-010）：每页 15 / 25 / 50 条；OM 结果窗口最多 10000 条（research R6）。 */
export function Pagination({
  total,
  windowLimited,
}: {
  total: number;
  windowLimited: boolean;
}) {
  const { criteria, dispatch } = useAssetsCriteria();
  const reachable = Math.min(total, RESULT_WINDOW);
  const pages = Math.max(1, Math.ceil(reachable / criteria.pageSize));
  const go = (page: number) => dispatch({ type: "page", page });
  return (
    <nav className="asset-pagination" aria-label="分页">
      <button
        type="button"
        disabled={criteria.page <= 1}
        onClick={() => go(criteria.page - 1)}
      >
        上一页
      </button>
      <span>
        第 {criteria.page} / {pages} 页
      </span>
      <button
        type="button"
        disabled={criteria.page >= pages}
        onClick={() => go(criteria.page + 1)}
      >
        下一页
      </button>
      <label>
        每页
        <select
          aria-label="每页条数"
          value={criteria.pageSize}
          onChange={(e) =>
            dispatch({ type: "pageSize", pageSize: Number(e.target.value) })
          }
        >
          {PAGE_SIZES.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        条
      </label>
      {windowLimited && (
        <span className="asset-pagination__hint">
          仅显示前 10000 条，请缩小条件
        </span>
      )}
    </nav>
  );
}
