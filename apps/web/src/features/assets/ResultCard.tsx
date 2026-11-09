import { Link } from "react-router";
import type {
  EntityRef,
  GovernanceSummary,
  SearchHit,
} from "@contexture/ts-api";
import { NavIcon } from "../../layout/NavIcon";
import { Highlight } from "./Highlight";
import { detailTarget } from "./links";
import { ORIGIN_LABEL, typeIcon, typeLabel } from "./labels";

export const refNames = (refs?: EntityRef[], empty = "未分配") =>
  refs?.length
    ? refs.map((r) => r.displayName || r.name || r.id).join("、")
    : empty;

/** 结果卡片（FR-011）：数据全部来自 OM 搜索结果。 */
export function ResultCard({
  hit,
  selected,
  onSelect,
}: {
  hit: SearchHit;
  selected: boolean;
  onSelect: () => void;
}) {
  const title = hit.displayName || hit.name;
  const target = detailTarget(hit.ref, hit.parentTable, hit.columnName);
  const g: GovernanceSummary = hit.governance ?? {};
  const matched = (hit.matchedFields ?? []).reduce((n, f) => n + f.count, 0);
  const name = <Highlight segments={hit.nameHighlight} fallback={title} />;
  return (
    <article
      aria-label={title}
      aria-current={selected ? "true" : undefined}
      className={`asset-card${selected ? " is-selected" : ""}`}
      onClick={onSelect}
    >
      {!!hit.breadcrumb?.length && (
        <div className="asset-card__crumb">
          {hit.breadcrumb.map((b) => b.label).join(" / ")}
        </div>
      )}
      <div className="asset-card__title">
        <NavIcon name={typeIcon(hit.ref.entityType)} />
        {target ? (
          <Link
            to={target.to}
            state={target.state}
            onClick={(e) => e.stopPropagation()}
          >
            {name}
          </Link>
        ) : (
          <span className="asset-card__name">{name}</span>
        )}
        <span className="asset-badge">{typeLabel(hit.ref.entityType)}</span>
        {g.certification && (
          <span className="asset-badge asset-badge--cert">
            <span>认证</span>
            <span>{g.certification}</span>
          </span>
        )}
      </div>
      <p className="asset-card__desc">
        <Highlight
          segments={hit.descriptionHighlight}
          fallback={hit.description || "暂无描述"}
        />
      </p>
      <div className="asset-card__meta">
        <span>
          <b>业务域</b>
          {refNames(g.domains)}
        </span>
        <span>
          <b>负责人</b>
          {refNames(g.owners)}
        </span>
        <span>
          <b>分级（Tier）</b>
          {g.tier ?? "未设置"}
        </span>
        <span>
          <b>数据安全级别</b>
          {g.dataLevel ?? "未设置"}
        </span>
        {matched > 0 && <span>命中 {matched} 处</span>}
        <span className={`asset-origin asset-origin--${hit.origin}`}>
          {ORIGIN_LABEL[hit.origin]}
        </span>
      </div>
    </article>
  );
}
