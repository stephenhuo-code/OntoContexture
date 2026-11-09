import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { PageState } from "@contexture/ui";
import type { SearchHit } from "@contexture/ts-api";
import { useAssetsCriteria } from "./criteria";
import { effectiveRequest } from "./explore";
import { useSearch, useTypeCounts } from "./queries";
import { ResultCard } from "./ResultCard";
import { SummaryPanel } from "./SummaryPanel";
import { SOURCES_BASE } from "../sources/format";

/** 探索视图（FR-001）：页头、结果卡片与只读摘要。数字与内容全部来自 BFF，不内置示例数据。 */
export function ExploreView() {
  const { criteria, dispatch } = useAssetsCriteria();
  const counts = useTypeCounts(criteria, !!criteria.keyword);
  const eff = effectiveRequest(criteria, counts.state);
  const result = useSearch(eff.body);
  const hits = result.state.status === "ready" ? result.state.data.hits : null;
  const [selected, setSelected] = useState<SearchHit | null>(null);
  // 结果更新后自动选中第一条；无结果时关闭摘要（FR-012）
  useEffect(() => {
    if (hits) setSelected(hits[0] ?? null);
  }, [hits]);
  useEffect(() => {
    if (eff.empty) setSelected(null);
  }, [eff.empty]);
  const close = useCallback(() => setSelected(null), []);
  const hasConditions =
    !!criteria.keyword ||
    criteria.browsePath.length > 0 ||
    Object.keys(criteria.filters).length > 0;
  const total =
    result.state.status === "ready"
      ? result.state.data.total
      : eff.empty
        ? 0
        : null;

  let body;
  if (eff.empty || (hits && hits.length === 0 && hasConditions))
    body = (
      <PageState
        kind="empty"
        title="无匹配结果"
        description="请调整关键词或筛选条件"
        actionLabel="清除条件"
        action={() => dispatch({ type: "clearAll" })}
      />
    );
  else if (hits && hits.length === 0)
    body = (
      <PageState
        kind="empty"
        title="尚未接入任何数据资产"
        description="可以在「添加数据源」中接入源库并采集元数据；开发环境也可以运行开发态元数据导入（make dev-metadata）。"
      />
    );
  else if (result.state.status === "error" || counts.state.status === "error") {
    const err =
      result.state.status === "error"
        ? result.state.error
        : counts.state.status === "error"
          ? counts.state.error
          : null;
    body = err && (
      <PageState
        kind="error"
        title={`搜索失败 · ${err.code}`}
        description={err.message}
        actionLabel="重试"
        action={() =>
          result.state.status === "error" ? result.reload() : counts.reload()
        }
        traceId={err.trace_id}
      />
    );
  } else if (!hits) body = <PageState kind="loading" title="正在搜索" />;
  else
    body = (
      <ul className="asset-results" aria-label="搜索结果">
        {hits.map((h) => (
          <li key={`${h.ref.entityType}:${h.ref.id}:${h.ref.fqn}`}>
            <ResultCard
              hit={h}
              selected={
                selected?.ref.fqn === h.ref.fqn &&
                selected.ref.entityType === h.ref.entityType
              }
              onSelect={() => setSelected(h)}
            />
          </li>
        ))}
      </ul>
    );

  return (
    <section className="asset-explore" aria-label="资产探索">
      <div className="asset-explore__head">
        <div>
          <h2>全部数据资产</h2>
          {total !== null && (
            <span className="asset-explore__count">共 {total} 条</span>
          )}
        </div>
        <div className="asset-explore__actions">
          <Link className="ctx-button ctx-button--secondary" to={SOURCES_BASE}>
            数据源管理
          </Link>
          <Link
            className="ctx-button ctx-button--primary"
            to={SOURCES_BASE}
            state={{ addSource: true }}
          >
            添加数据源
          </Link>
        </div>
      </div>
      <div className={`asset-explore__body${selected ? " has-summary" : ""}`}>
        <div className="asset-explore__results">{body}</div>
        {selected && hits && hits.length > 0 && (
          <SummaryPanel
            key={`${selected.ref.entityType}:${selected.ref.fqn}`}
            hit={selected}
            onClose={close}
          />
        )}
      </div>
    </section>
  );
}
