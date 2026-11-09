import { useEffect, useState } from "react";
import { Link } from "react-router";
import { PageState } from "@contexture/ui";
import type {
  AssetSummary,
  SearchHit,
  SummaryColumn,
} from "@contexture/ts-api";
import { detailTarget } from "./links";
import { ORIGIN_LABEL, typeLabel } from "./labels";
import { useSummary } from "./queries";
import { refNames } from "./ResultCard";

const CONSTRAINT: Record<string, string> = {
  PRIMARY_KEY: "主键",
  UNIQUE: "唯一",
};
const list = (items?: string[]) => (items?.length ? items.join("、") : "—");

function Overview({ s }: { s: AssetSummary }) {
  const g = s.governance;
  const rows: [string, string][] = [
    ["描述", s.description || "暂无描述"],
    ["负责人", refNames(g.owners)],
    ["业务域", refNames(g.domains)],
    ["分级（Tier）", g.tier ?? "未设置"],
    ["数据安全级别", g.dataLevel ?? "未设置"],
    ["认证", g.certification ?? "—"],
    ["业务术语", list(g.glossaryTerms)],
    ["分类标签", list(g.tags)],
    ["数据产品", refNames(g.dataProducts, "—")],
    ["来源", g.origin ? ORIGIN_LABEL[g.origin] : "—"],
  ];
  return (
    <dl className="summary-kv">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Columns({ columns }: { columns: SummaryColumn[] }) {
  if (!columns.length) return <p className="catalog-note">没有字段</p>;
  return (
    <table className="summary-columns">
      <thead>
        <tr>
          <th>名称</th>
          <th>类型</th>
          <th>约束</th>
          <th>描述</th>
          <th>分类标签</th>
        </tr>
      </thead>
      <tbody>
        {columns.map((c) => (
          <tr key={c.name}>
            <td>{c.name}</td>
            <td>{c.dataTypeDisplay ?? "—"}</td>
            <td>
              {c.constraint ? (CONSTRAINT[c.constraint] ?? c.constraint) : "—"}
            </td>
            <td>{c.description || "—"}</td>
            <td>{list(c.tags)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** 只读摘要（FR-012、D6）：页签为「概览」「Schema」；按选中资产的身份读取 OM 实体。 */
export function SummaryPanel({
  hit,
  onClose,
}: {
  hit: SearchHit;
  onClose: () => void;
}) {
  const summary = useSummary(hit.ref.entityType, hit.ref.fqn);
  const [tab, setTab] = useState<"overview" | "schema">("overview");
  const hasSchema =
    hit.ref.entityType === "table" || hit.ref.entityType === "tableColumn";
  useEffect(() => setTab("overview"), [hit.ref.fqn]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  const title = hit.displayName || hit.name;
  const target = detailTarget(hit.ref, hit.parentTable, hit.columnName);
  const s = summary.state;
  // 列没有独立的实体 id，摘要读取所属表，不按 id 比对（research R10）
  const mismatch =
    s.status === "ready" &&
    hit.ref.entityType !== "tableColumn" &&
    s.data.ref.id !== hit.ref.id;
  return (
    <aside className="asset-summary" aria-label="资产摘要">
      <header className="asset-summary__head">
        <div>
          <small>{typeLabel(hit.ref.entityType)}</small>
          <h3>
            {target ? (
              <Link to={target.to} state={target.state}>
                {title}
              </Link>
            ) : (
              title
            )}
          </h3>
          <small className="asset-summary__fqn">{hit.ref.fqn}</small>
        </div>
        <button
          type="button"
          className="link-button"
          aria-label="关闭摘要"
          onClick={onClose}
        >
          ✕
        </button>
      </header>
      <div role="tablist" className="asset-summary__tabs">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "overview"}
          onClick={() => setTab("overview")}
        >
          概览
        </button>
        {hasSchema && (
          <button
            type="button"
            role="tab"
            aria-selected={tab === "schema"}
            onClick={() => setTab("schema")}
          >
            Schema
          </button>
        )}
      </div>
      {s.status === "loading" && (
        <PageState kind="loading" title="正在读取摘要" />
      )}
      {s.status === "error" && (
        <PageState
          kind="error"
          title={`摘要读取失败 · ${s.error.code}`}
          description={s.error.message}
          actionLabel="重试"
          action={summary.reload}
          traceId={s.error.trace_id}
        />
      )}
      {mismatch && (
        <PageState
          kind="error"
          title="摘要与所选资产不一致"
          description="请重新选择该资产"
        />
      )}
      {s.status === "ready" && !mismatch && (
        <div role="tabpanel">
          {tab === "overview" ? (
            <Overview s={s.data} />
          ) : (
            <Columns
              columns={s.data.columns ?? (s.data.column ? [s.data.column] : [])}
            />
          )}
        </div>
      )}
    </aside>
  );
}
