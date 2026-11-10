import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { PageState } from "@contexture/ui";
import type {
  EntityRef,
  GlossaryTermDetail,
  TagDetail,
} from "@contexture/ts-api";
import { glossaryTermDetail, tagDetail } from "./api";
import { ORIGIN_LABEL } from "./labels";
import { ASSETS_KEY, toLoad } from "./queries";
import { refNames } from "./ResultCard";

const dash = (v?: string | null) => (v ? v : "—");
const names = (refs?: (EntityRef | null)[] | null) =>
  refs?.filter(Boolean).length
    ? refs
        .filter((r): r is EntityRef => !!r)
        .map((r) => r.displayName || r.name || r.id)
        .join("、")
    : "—";

function Fields({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="summary-kv governance-detail__fields">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function termRows(d: GlossaryTermDetail): [string, string][] {
  return [
    ["名称", d.name],
    ["显示名称", dash(d.displayName)],
    ["完整名称（FQN）", d.ref.fqn],
    ["所属术语表", names([d.glossary ?? null])],
    ["上级术语", names([d.parent ?? null])],
    ["描述", dash(d.description)],
    ["同义词", d.synonyms?.length ? d.synonyms.join("、") : "—"],
    ["相关术语", names(d.relatedTerms)],
    [
      "参考链接",
      d.references?.length
        ? d.references.map((r) => `${r.name}（${r.endpoint}）`).join("、")
        : "—",
    ],
    ["负责人", refNames(d.owners)],
    ["评审人", refNames(d.reviewers, "未设置")],
    ["业务域", refNames(d.domains)],
    ["分类标签", d.tags?.length ? d.tags.join("、") : "—"],
    ["状态", dash(d.entityStatus)],
  ];
}

function tagRows(d: TagDetail): [string, string][] {
  return [
    ["名称", d.name],
    ["显示名称", dash(d.displayName)],
    ["完整名称（FQN）", d.ref.fqn],
    ["所属分类", names([d.classification ?? null])],
    ["上级标签", names([d.parent ?? null])],
    ["描述", dash(d.description)],
    ["负责人", refNames(d.owners)],
    ["评审人", refNames(d.reviewers, "未设置")],
    ["业务域", refNames(d.domains)],
    ["是否已弃用", d.deprecated ? "已弃用" : "否"],
  ];
}

/**
 * 业务术语 / 分类标签只读详情（FR-013）：字段取自 OM 实体原生字段（research R9，负责人 2026-11-09 确认），
 * 没有编辑入口；实体不存在时显示真实的「未找到」错误。
 */
export function GovernanceDetail({ kind }: { kind: "glossaryTerm" | "tag" }) {
  const { fqn = "" } = useParams();
  const q = useQuery({
    queryKey: [...ASSETS_KEY, kind, fqn],
    queryFn: (): Promise<GlossaryTermDetail | TagDetail> =>
      kind === "glossaryTerm" ? glossaryTermDetail(fqn) : tagDetail(fqn),
    retry: false,
    refetchOnWindowFocus: false,
  });
  const state = toLoad(q);
  const title = kind === "glossaryTerm" ? "业务术语详情" : "分类标签详情";
  const back = (
    <Link to="/assets" className="back-link">
      返回探索视图
    </Link>
  );
  if (state.status === "loading")
    return <PageState kind="loading" title={`正在读取${title}`} />;
  if (state.status === "error")
    return (
      <>
        {back}
        <PageState
          kind="error"
          title={`${state.error.code === "catalog.not_found" ? "未找到" : "读取失败"} · ${state.error.code}`}
          description={state.error.message}
          actionLabel="重试"
          action={() => void q.refetch()}
          traceId={state.error.trace_id}
        />
      </>
    );
  const d = state.data;
  return (
    <section className="ctx-panel governance-detail" aria-label={title}>
      {back}
      <div className="governance-detail__head">
        <small>{title}（只读）</small>
        <h2>{d.displayName || d.name}</h2>
        {"origin" in d && d.origin && (
          <span className={`asset-origin asset-origin--${d.origin}`}>
            {ORIGIN_LABEL[d.origin]}
          </span>
        )}
      </div>
      <Fields
        rows={
          kind === "glossaryTerm"
            ? termRows(d as GlossaryTermDetail)
            : tagRows(d as TagDetail)
        }
      />
    </section>
  );
}
