import type { CatalogEntity } from "@contexture/ts-api";
import { KIND_NAME } from "./format";

type Ref = { name?: string; displayName?: string; fullyQualifiedName?: string };

export function Chips({ items }: { items: string[] }) {
  return items.length ? (
    <span className="chips">
      {items.map((x) => (
        <span key={x} className="chip">
          {x}
        </span>
      ))}
    </span>
  ) : (
    <span className="muted">未分配</span>
  );
}

const names = (refs?: Ref[]) =>
  (refs ?? []).map(
    (r) => r.displayName || r.name || r.fullyQualifiedName || "",
  );

/** 资产属性卡片（只读，值来自 OpenMetadata；US4 增加继承标注与编辑） */
export function AssetProperties({ entity }: { entity: CatalogEntity }) {
  const g = entity.governance ?? {};
  const kind = KIND_NAME[entity.entityType];
  return (
    <section className="ctx-panel asset-properties" aria-label={`${kind}属性`}>
      <h3>
        {kind}属性 · {g.displayName || entity.name}
      </h3>
      <div className="detail-grid">
        <dl className="kv">
          <dt>名称（只读）</dt>
          <dd className="mono">{entity.name}</dd>
          <dt>显示名称</dt>
          <dd>{g.displayName || "未设置"}</dd>
          <dt>完整名称</dt>
          <dd className="mono">{entity.fullyQualifiedName}</dd>
          <dt>描述</dt>
          <dd className="pre">{g.description || "暂无描述"}</dd>
          <dt>负责人</dt>
          <dd>
            <Chips items={names(g.owners)} />
          </dd>
          {entity.entityType !== "databaseService" && (
            <>
              <dt>保留周期</dt>
              <dd>{g.retentionPeriod || "未设置"}</dd>
            </>
          )}
        </dl>
        <dl className="kv">
          <dt>业务域</dt>
          <dd>
            <Chips items={names(g.domains)} />
          </dd>
          <dt>重要程度</dt>
          <dd>{g.tier || "未设置"}</dd>
          <dt>分类标签</dt>
          <dd>
            <Chips items={g.tags ?? []} />
          </dd>
          <dt>业务术语</dt>
          <dd>
            <Chips items={g.glossaryTerms ?? []} />
          </dd>
          <dt>数据产品</dt>
          <dd>
            <Chips items={names(g.dataProducts)} />
          </dd>
        </dl>
      </div>
    </section>
  );
}
